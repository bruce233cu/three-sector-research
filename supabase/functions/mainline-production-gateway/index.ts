import {createClient} from "npm:@supabase/supabase-js@2.95.0";
import {createRemoteJWKSet,jwtVerify} from "npm:jose@6.1.0";
const jwks=createRemoteJWKSet(new URL("https://token.actions.githubusercontent.com/.well-known/jwks"));
const respond=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{"content-type":"application/json","cache-control":"no-store"}});
Deno.serve(async(req:Request)=>{
 if(req.method!=="POST")return respond({error:"method_not_allowed"},405);
 try{
  const token=(req.headers.get("authorization")||"").replace(/^Bearer /,"");
  const {payload}=await jwtVerify(token,jwks,{issuer:"https://token.actions.githubusercontent.com",audience:"mainline-production"});
  if(payload.repository!=="bruce233cu/three-sector-research"||payload.ref!=="refs/heads/mainline-phase1e"||payload.workflow_ref!=="bruce233cu/three-sector-research/.github/workflows/mainline-production.yml@refs/heads/mainline-phase1e")return respond({error:"untrusted_workflow"},403);
  const b=await req.json();
  const c=createClient(Deno.env.get("SUPABASE_URL")!,Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,{auth:{persistSession:false}});
  if(b.operation==="context"){
   const {data,error}=await c.rpc("mainline_production_context",{p_date:b.trade_date});if(error)throw error;return respond(data);
  }
  if(b.operation==="validation_input"){
   const {data,error}=await c.rpc("mainline_validation_input",{p_date:b.trade_date});if(error)throw error;return respond(data);
  }
  if(b.operation==="attempt"){
   if(b.payload.code_sha!==payload.sha)return respond({error:"code_sha_mismatch"},403);
   const {data,error}=await c.rpc("mainline_attempt_trace",{p_payload:b.payload});if(error)throw error;return respond(data);
  }
  if(b.operation==="commit"){
   if(b.payload.code_sha!==payload.sha)return respond({error:"code_sha_mismatch"},403);
   const {data,error}=await c.rpc("mainline_commit_day",{p_payload:b.payload});if(error)throw error;return respond(data);
  }
  return respond({error:"invalid_operation"},400);
 }catch(e){return respond({error:String(e)},400);}
});
