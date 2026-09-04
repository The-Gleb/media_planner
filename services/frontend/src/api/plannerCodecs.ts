import { parseMoney } from '../domain/numeric'
import type { Allocation, KPI, MediaPlan } from '../domain/planning'

type R = Record<string, unknown>
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i
const MONEY6 = /^(0|[1-9][0-9]*)\.[0-9]{6}$/
const CHANNEL = /^[a-z][a-z0-9_-]{0,63}$/
const KEYS = ['request_id','state_revision','plan_id','feasible','type','strategy','optimize','currency','budget','horizon','expected','allocations','required_budget','reason']
const object = (v: unknown, name: string): R => { if (!v || typeof v !== 'object' || Array.isArray(v)) throw new Error(`invalid_${name}`); return v as R }
const exact = (v: R, keys: readonly string[], name: string) => { const got=Object.keys(v).sort(); const want=[...keys].sort(); if(got.length!==want.length||got.some((k,i)=>k!==want[i])) throw new Error(`invalid_${name}_fields`) }
const integer = (v: unknown, min: number, max: number) => typeof v === 'number' && Number.isSafeInteger(v) && v >= min && v <= max
const money6 = (v: unknown): v is string => { if(typeof v!== 'string'||!MONEY6.test(v)) return false; try{parseMoney(v);return true}catch{return false} }

export function decodeMediaPlan(raw: unknown): MediaPlan {
  const value=object(raw,'plan'); exact(value,KEYS,'plan')
  const horizon=object(value.horizon,'plan_horizon'); exact(horizon,['from_hour','to_hour'],'plan_horizon')
  if(typeof value.request_id!=='string'||!UUID.test(value.request_id)||typeof value.plan_id!=='string'||!/^[a-f0-9]{64}$/.test(value.plan_id)
    ||!integer(value.state_revision,0,2160)||value.feasible!==true||value.type!=='fixed_budget'||!['uniform','optimized'].includes(String(value.strategy))
    ||!['unique_reach','clicks','conversions'].includes(String(value.optimize))||typeof value.currency!=='string'||!/^[A-Z]{3}$/.test(value.currency)
    ||!money6(value.budget)||!integer(horizon.from_hour,0,2159)||!integer(horizon.to_hour,1,2160)||(horizon.from_hour as number)>=(horizon.to_hour as number)
    ||value.expected!==null||value.required_budget!==null||value.reason!==null||!Array.isArray(value.allocations)||value.allocations.length<1||value.allocations.length>43200) throw new Error('invalid_plan')
  const allocations: Allocation[]=value.allocations.map((rawItem)=>{const item=object(rawItem,'plan_allocation'); exact(item,['channel_id','hour','budget_cap','expected'],'plan_allocation')
    if(typeof item.channel_id!=='string'||!CHANNEL.test(item.channel_id)||!integer(item.hour,0,2159)||!money6(item.budget_cap)||item.expected!==null) throw new Error('invalid_plan_allocation')
    return {channelId:item.channel_id,hour:item.hour as number,budgetCap:item.budget_cap,expected:null}})
  for(let i=1;i<allocations.length;i++){const a=allocations[i-1],b=allocations[i];if(a.hour>b.hour||(a.hour===b.hour&&a.channelId>=b.channelId)) throw new Error('invalid_plan_order')}
  return {requestId:value.request_id,stateRevision:value.state_revision as number,planId:value.plan_id,feasible:true,type:'fixed_budget',strategy:value.strategy as MediaPlan['strategy'],optimize:value.optimize as KPI,currency:value.currency,budget:value.budget,horizon:{fromHour:horizon.from_hour as number,toHour:horizon.to_hour as number},expected:null,allocations,requiredBudget:null,reason:null}
}
export function validatePlanCoverage(plan: MediaPlan, channelIds: readonly string[]): void {
  const sorted=[...channelIds].sort(); if(new Set(sorted).size!==sorted.length) throw new Error('invalid_plan_channels')
  const expectedCount=(plan.horizon.toHour-plan.horizon.fromHour)*sorted.length
  if(plan.allocations.length!==expectedCount) throw new Error('invalid_plan_coverage')
  let sum=0n,index=0
  for(let hour=plan.horizon.fromHour;hour<plan.horizon.toHour;hour++) for(const channel of sorted){const item=plan.allocations[index++];if(item.hour!==hour||item.channelId!==channel) throw new Error('invalid_plan_coverage');sum+=parseMoney(item.budgetCap)}
  if(sum!==parseMoney(plan.budget)) throw new Error('invalid_plan_total')
}
