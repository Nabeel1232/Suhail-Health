import {type NextRequest} from 'next/server';
export const runtime='nodejs';
export const dynamic='force-dynamic';
export const maxDuration=180;
async function proxy(request:NextRequest,context:{params:Promise<{path:string[]}>}) {
  const {path}=await context.params;
  const base=(process.env.API_INTERNAL_URL||'http://127.0.0.1:18000').replace(/\/$/,'');
  const destination=`${base}/${path.map(encodeURIComponent).join('/')}${request.nextUrl.search}`;
  const headers=new Headers();
  for(const name of ['cookie','content-type','origin','accept']) {const v=request.headers.get(name);if(v)headers.set(name,v)}
  try {
    const response=await fetch(destination,{method:request.method,headers,body:request.method==='POST'?await request.arrayBuffer():undefined,cache:'no-store',redirect:'manual',signal:AbortSignal.timeout(165000)});
    const outgoing=new Headers();
    for(const name of ['content-type','content-disposition','cache-control','x-content-type-options','referrer-policy']){const v=response.headers.get(name);if(v)outgoing.set(name,v)}
    for(const cookie of response.headers.getSetCookie())outgoing.append('set-cookie',cookie);
    outgoing.set('cache-control','no-store');
    return new Response(response.body,{status:response.status,headers:outgoing});
  } catch {return Response.json({detail:'The care coordination service is temporarily unavailable. Please try again or contact your assigned support team.'},{status:502})}
}
export const GET=proxy;
export const POST=proxy;
