import { decodeMediaPlan } from './plannerCodecs'
import { decodePlannerProblem, PlannerProblemError } from './problem'
import type { FixedBudgetPlanRequest } from '../domain/planning'
export class PlannerClient {
  constructor(private readonly fetcher: typeof fetch = globalThis.fetch.bind(globalThis),private readonly timeoutMs=20_000) {}
  private async timedFetch(input:string,init:RequestInit={}):Promise<Response>{const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),this.timeoutMs);try{return await this.fetcher(input,{...init,signal:controller.signal})}finally{clearTimeout(timer)}}
  async ready():Promise<boolean>{try{const r=await this.timedFetch('/planner-api/health/ready',{headers:{Accept:'application/json'}});if(!r.ok)return false;const body=await r.json();return Boolean(body&&typeof body==='object'&&!Array.isArray(body)&&Object.keys(body).length===1&&(body as Record<string,unknown>).status==='ok')}catch{return false}}
  async plan(payload:FixedBudgetPlanRequest){let response:Response;try{response=await this.timedFetch('/planner-api/v1/plans',{method:'POST',headers:{Accept:'application/json','Content-Type':'application/json','X-Request-ID':payload.request_id},body:JSON.stringify(payload)})}catch(cause){throw new Error('planner_unreachable',{cause})}if(!response.ok){let body:unknown={};try{body=await response.json()}catch{/* proxy failure */}throw new PlannerProblemError(decodePlannerProblem(body,response.status))}try{return decodeMediaPlan(await response.json())}catch(cause){throw new Error('planner_invalid_response',{cause})}}
}
export const plannerClient=new PlannerClient()
