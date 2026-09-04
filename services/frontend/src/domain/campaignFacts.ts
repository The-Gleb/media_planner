import { addMoney } from './numeric'
import type { CampaignFacts, ChannelFacts } from './planning'
import type { HourlyResult } from './types'
const zeroChannel=():ChannelFacts=>({spent:'0.000000',requests:'0',impressions:'0',uniqueReach:'0',clicks:'0',conversions:'0'})
export function zeroCampaignFacts(channelIds:readonly string[]):CampaignFacts { return {currentHour:0,stateRevision:0,lastStepId:null,lastObservedAt:null,spent:'0.000000',uniqueReach:'0',clicks:'0',conversions:'0',channels:Object.fromEntries(channelIds.map(id=>[id,zeroChannel()]))} }
const plus=(a:string,b:bigint)=>(BigInt(a)+b).toString()
export function accumulateFacts(current:CampaignFacts,result:HourlyResult):CampaignFacts { if(current.lastStepId===result.stepId) throw new Error('duplicate_fact_commit'); const channels={...current.channels}; let spend='0.000000',reach=0n,clicks=0n,conversions=0n
 for(const o of result.observations){const previous=channels[o.channelId];if(!previous)throw new Error('facts_unknown_channel');channels[o.channelId]={spent:addMoney(previous.spent,o.spend),requests:plus(previous.requests,o.requests),impressions:plus(previous.impressions,o.impressions),uniqueReach:plus(previous.uniqueReach,o.uniqueReach),clicks:plus(previous.clicks,o.clicks),conversions:plus(previous.conversions,o.conversions)};spend=addMoney(spend,o.spend);reach+=o.uniqueReach;clicks+=o.clicks;conversions+=o.conversions}
 return {currentHour:current.currentHour+1,stateRevision:current.stateRevision+1,lastStepId:result.stepId,lastObservedAt:result.observedHour,spent:addMoney(current.spent,spend),uniqueReach:plus(current.uniqueReach,reach),clicks:plus(current.clicks,clicks),conversions:plus(current.conversions,conversions),channels} }
