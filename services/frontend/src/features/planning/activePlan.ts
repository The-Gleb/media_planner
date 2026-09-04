import { validatePlanCoverage } from '../../api/plannerCodecs'
import type { ActivePlan, MediaPlan, PlanRequest } from '../../domain/planning'
export function activatePlan(plan:MediaPlan,requestId:string,revision:number,channels:readonly string[],previousPlanId?:string,request?:PlanRequest):ActivePlan {
 if(plan.requestId!==requestId||plan.stateRevision!==revision||(previousPlanId!==undefined&&plan.planId!==previousPlanId)) throw new Error('stale_plan')
 if(request&&(plan.currency!==request.simulation.currency||plan.strategy!==request.strategy||plan.horizon.fromHour!==request.horizon.from_hour||plan.horizon.toHour!==request.horizon.to_hour)) throw new Error('stale_plan')
 if(request?.type==='fixed_budget'&&(plan.type!=='fixed_budget'||plan.budget!==request.budget||plan.optimize!==request.optimize)) throw new Error('stale_plan')
 if(request?.type==='target_kpi'&&(plan.type!=='target_kpi'||plan.target?.metric!==request.target.metric||plan.target.value!==request.target.value||plan.requiredBudget!==plan.budget)) throw new Error('stale_plan')
 validatePlanCoverage(plan,channels); const mutable=new Map<number,ReadonlyMap<string,string>>(), building=new Map<number,Map<string,string>>(); for(const allocation of plan.allocations){let values=building.get(allocation.hour);if(!values){values=new Map<string,string>();building.set(allocation.hour,values);mutable.set(allocation.hour,values)}values.set(allocation.channelId,allocation.budgetCap)}
 return {...plan,index:mutable}
}
