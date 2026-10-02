import { NextResponse } from 'next/server';
export async function GET(request:Request) {
 const url=process.env.SUPABASE_URL;const key=process.env.SUPABASE_PUBLISHABLE_KEY;
 if(!url||!key)return NextResponse.json({error:'mainline runtime configuration missing'},{status:503});
 const input=new URL(request.url);const params=new URLSearchParams();
 for(const name of ['kind','object','date']){const value=input.searchParams.get(name);if(value)params.set(name,value);}
 try{
  const response=await fetch(`${url}/functions/v1/mainline-status?${params}`,{headers:{apikey:key},cache:'no-store'});
  if(!response.ok)return NextResponse.json({error:'mainline status unavailable'},{status:response.status>=500?502:response.status});
  return new NextResponse(await response.text(),{headers:{'content-type':'application/json; charset=utf-8','cache-control':'no-store'}});
 }catch{return NextResponse.json({error:'mainline status unavailable'},{status:502});}
}
