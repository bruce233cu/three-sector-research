import {createClient} from 'npm:@supabase/supabase-js@2.95.0';
const json=(body:unknown,status=200)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
Deno.serve(async(req:Request)=>{
 if(req.method!=='GET')return json({error:'method_not_allowed'},405);
 const supplied=req.headers.get('apikey');
 const accepted=[Deno.env.get('SUPABASE_ANON_KEY'),Deno.env.get('SB_PUBLISHABLE_KEY'),'sb_publishable_dlxzdLwKH7tWItodKLGCxA_GS5P-8Zh'].filter(Boolean);
 if(!supplied||!accepted.includes(supplied))return json({error:'unauthorized'},401);
 const u=new URL(req.url);const kind=u.searchParams.get('kind')||'summary';const object=u.searchParams.get('object');const date=u.searchParams.get('date');
 if(!['summary','radar','detail','timeline'].includes(kind)||object&&!/^sw1_classification_\d{6}$/.test(object)||date&&!/^\d{4}-\d{2}-\d{2}$/.test(date))return json({error:'invalid_read_parameters'},400);
 const c=createClient(Deno.env.get('SUPABASE_URL')!,Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,{auth:{persistSession:false}});
 const {data,error}=await c.rpc('mainline_status_read',{p_kind:kind,p_object:object,p_date:date});
 if(error)return json({error:'mainline_query_failed'},500);
 return json({...data,production_readiness:{dispatch_credential_configured:Boolean(Deno.env.get('MAINLINE_GITHUB_DISPATCH_TOKEN'))}});
});
