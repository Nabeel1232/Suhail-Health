import {Shell} from '@/components/shell';
import {CaseDetail} from '@/components/care';
export default async function Page({params}:{params:Promise<{id:string}>}){const {id}=await params;return <Shell><CaseDetail id={id}/></Shell>}
