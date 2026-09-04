import { useCallback, useRef } from 'react'
import { plannerClient } from '../../api/plannerClient'
import type { FixedBudgetPlanRequest, MediaPlan, PendingPlanningRound } from '../../domain/planning'
import type { CampaignAction } from '../campaign/campaignState'
import { userError } from '../../app/messages'
import { acceptPlanningRound, createPlanningRound, retryPlanningRound } from './planningRound'
export function usePlanningController(channels:readonly string[],dispatch:(action:CampaignAction)=>void){const pendingRoundRef=useRef<PendingPlanningRound|null>(null)
 const prepare=useCallback((request:FixedBudgetPlanRequest,expectedPlanId:string|null,presentation?:MediaPlan)=>{const targetPresentation=presentation?.type==='target_kpi'?{type:presentation.type,target:presentation.target,expected:presentation.expected,requiredBudget:presentation.requiredBudget}:null;const round=createPlanningRound(request,expectedPlanId,targetPresentation);pendingRoundRef.current=round;return round},[])
 const submit=useCallback(async(round:PendingPlanningRound)=>{try{const plan=await plannerClient.plan(round.request),current=pendingRoundRef.current;if(!plan.feasible)throw new Error('planner_invalid_response');if(!current||current.requestId!==round.requestId||current.stateRevision!==round.stateRevision)throw new Error('stale_plan');const activePlan=acceptPlanningRound(round,plan,channels);pendingRoundRef.current=null;dispatch({type:'replanned',activePlan});return activePlan}catch(error){if(pendingRoundRef.current?.requestId===round.requestId)dispatch({type:'replan-failed',error:userError(error,'Перепланирование'),pendingRound:round});throw error}},[channels,dispatch])
 const retry=useCallback(async()=>{const current=pendingRoundRef.current;if(!current)throw new Error('missing_planning_round');const round=retryPlanningRound(current);pendingRoundRef.current=round;dispatch({type:'retry-replan',pendingRound:round});return submit(round)},[dispatch,submit])
 return{pendingRoundRef,prepare,submit,retry}}
