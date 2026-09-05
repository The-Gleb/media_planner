import { parseMoney } from '../domain/numeric'
import type { Allocation, ExpectedOutcome, KPI, MediaPlan, PlanResult, TargetKPI } from '../domain/planning'

type R = Record<string, unknown>
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const MONEY6 = /^(0|[1-9][0-9]*)\.[0-9]{6}$/
const COUNT = /^(0|[1-9][0-9]*)$/
const CHANNEL = /^[a-z][a-z0-9_-]{0,63}$/
const KEYS = ['request_id','state_revision','plan_id','feasible','type','strategy','optimize','currency','budget','unallocated_budget','horizon','expected','allocations','required_budget','reason','target']
const object = (v: unknown, name: string): R => { if (!v || typeof v !== 'object' || Array.isArray(v)) throw new Error(`invalid_${name}`); return v as R }
const exact = (v: R, keys: readonly string[], name: string) => { const got=Object.keys(v).sort(); const want=[...keys].sort(); if(got.length!==want.length||got.some((k,i)=>k!==want[i])) throw new Error(`invalid_${name}_fields`) }
const integer = (v: unknown, min: number, max: number) => typeof v === 'number' && Number.isSafeInteger(v) && v >= min && v <= max
const money6 = (v: unknown): v is string => { if(typeof v!== 'string'||!MONEY6.test(v)) return false; try{parseMoney(v);return true}catch{return false} }
const count = (v:unknown):v is string => typeof v==='string'&&COUNT.test(v)

function decodeTarget(raw:unknown):TargetKPI { const value=object(raw,'target');exact(value,['metric','value'],'target');if(!['unique_reach','clicks','conversions'].includes(String(value.metric))||!count(value.value)||value.value==='0')throw new Error('invalid_target');return{metric:value.metric as KPI,value:value.value} }
function decodeExpected(raw:unknown):ExpectedOutcome { const value=object(raw,'expected');exact(value,['spend','impressions','unique_reach','clicks','conversions'],'expected');if(!money6(value.spend)||!count(value.impressions)||!count(value.unique_reach)||!count(value.clicks)||!count(value.conversions))throw new Error('invalid_expected');return{spend:value.spend,impressions:value.impressions,uniqueReach:value.unique_reach,clicks:value.clicks,conversions:value.conversions} }
function decodeAllocations(raw:unknown):Allocation[]{if(!Array.isArray(raw)||raw.length<1||raw.length>43200)throw new Error('invalid_plan_allocations');const allocations=raw.map((rawItem)=>{const item=object(rawItem,'plan_allocation');exact(item,['channel_id','hour','budget_cap','expected'],'plan_allocation');if(typeof item.channel_id!=='string'||!CHANNEL.test(item.channel_id)||!integer(item.hour,0,2159)||!money6(item.budget_cap)||item.expected!==null)throw new Error('invalid_plan_allocation');return{channelId:item.channel_id,hour:item.hour as number,budgetCap:item.budget_cap,expected:null}});for(let i=1;i<allocations.length;i++){const a=allocations[i-1],b=allocations[i];if(a.hour>b.hour||(a.hour===b.hour&&a.channelId>=b.channelId))throw new Error('invalid_plan_order')}return allocations}

export function decodePlanResult(raw: unknown): PlanResult {
  const value=object(raw,'plan'); exact(value,KEYS,'plan')
  const horizon=object(value.horizon,'plan_horizon'); exact(horizon,['from_hour','to_hour'],'plan_horizon')
  if(typeof value.request_id!=='string'||!UUID.test(value.request_id)||!integer(value.state_revision,0,2160)
    ||!['fixed_budget','target_kpi'].includes(String(value.type))||!['uniform','optimized'].includes(String(value.strategy))
    ||!['unique_reach','clicks','conversions'].includes(String(value.optimize))||typeof value.currency!=='string'||!/^[A-Z]{3}$/.test(value.currency)
    ||!integer(horizon.from_hour,0,2159)||!integer(horizon.to_hour,1,2160)||(horizon.from_hour as number)>=(horizon.to_hour as number)) throw new Error('invalid_plan')
  const common={requestId:value.request_id,stateRevision:value.state_revision as number,type:value.type as MediaPlan['type'],strategy:value.strategy as MediaPlan['strategy'],optimize:value.optimize as KPI,currency:value.currency,horizon:{fromHour:horizon.from_hour as number,toHour:horizon.to_hour as number}}
  if(value.feasible===false){
    if(value.type!=='target_kpi'||value.strategy!=='optimized'||value.state_revision!==0||value.plan_id!==null||value.budget!==null||value.unallocated_budget!==null||value.required_budget!==null||!Array.isArray(value.allocations)||value.allocations.length!==0)throw new Error('invalid_infeasible_plan')
    const reason=object(value.reason,'reason');exact(reason,['code','detail','max_achievable','recommended_target'],'reason');if(reason.code!=='target_exceeds_capacity'||typeof reason.detail!=='string'||!count(reason.max_achievable)||!count(reason.recommended_target))throw new Error('invalid_reason')
    return {...common,stateRevision:0,planId:null,feasible:false,type:'target_kpi',strategy:'optimized',budget:null,unallocatedBudget:null,expected:decodeExpected(value.expected),allocations:[],requiredBudget:null,target:decodeTarget(value.target),reason:{code:'target_exceeds_capacity',detail:reason.detail,maxAchievable:reason.max_achievable,recommendedTarget:reason.recommended_target}}
  }
  if(value.feasible!==true||typeof value.plan_id!=='string'||!/^[a-f0-9]{64}$/.test(value.plan_id)||!money6(value.budget)||!money6(value.unallocated_budget)||value.reason!==null)throw new Error('invalid_plan')
  const allocations=decodeAllocations(value.allocations)
  if(value.type==='fixed_budget'){
    if(value.expected!==null||value.required_budget!==null||value.target!==null)throw new Error('invalid_fixed_plan')
    return {...common,planId:value.plan_id,feasible:true,type:'fixed_budget',budget:value.budget,unallocatedBudget:value.unallocated_budget,expected:null,allocations,requiredBudget:null,reason:null,target:null}
  }
  if(value.strategy!=='optimized'||!money6(value.required_budget)||value.required_budget!==value.budget)throw new Error('invalid_target_plan')
  return {...common,planId:value.plan_id,feasible:true,type:'target_kpi',strategy:'optimized',budget:value.budget,unallocatedBudget:value.unallocated_budget,expected:decodeExpected(value.expected),allocations,requiredBudget:value.required_budget,reason:null,target:decodeTarget(value.target)}
}

export function decodeMediaPlan(raw:unknown):MediaPlan {const result=decodePlanResult(raw);if(!result.feasible)throw new Error('plan_is_infeasible');return result}
export function validatePlanCoverage(plan: MediaPlan, channelIds: readonly string[]): void {
  const sorted=[...channelIds].sort(); if(new Set(sorted).size!==sorted.length) throw new Error('invalid_plan_channels')
  const expectedCount=(plan.horizon.toHour-plan.horizon.fromHour)*sorted.length
  if(plan.allocations.length!==expectedCount) throw new Error('invalid_plan_coverage')
  let sum=0n,index=0
  for(let hour=plan.horizon.fromHour;hour<plan.horizon.toHour;hour++) for(const channel of sorted){const item=plan.allocations[index++];if(item.hour!==hour||item.channelId!==channel) throw new Error('invalid_plan_coverage');sum+=parseMoney(item.budgetCap)}
  if(sum+parseMoney(plan.unallocatedBudget)!==parseMoney(plan.budget)) throw new Error('invalid_plan_total')
}
