import asyncio
from types import SimpleNamespace
from evals.scheduling import round_robin,pace_gateway


def test_round_robin_preserves_selected_cases_and_prioritizes_each_group():
    groups=[[{'id':f'{agent}-{i}'} for i in range(3)] for agent in ('intake','router','safety')]
    scheduled=round_robin(groups)
    assert [x['id'] for x in scheduled[:3]]==['intake-0','router-0','safety-0']
    assert {x['id'] for x in scheduled}=={x['id'] for group in groups for x in group}


def test_pacing_applies_to_every_sdk_dispatch_without_changing_request():
    async def run():
        elapsed=[0.0];observed=[];waits=[]
        async def sleep(seconds):waits.append(seconds);elapsed[0]+=seconds
        async def create(**kwargs):observed.append((elapsed[0],kwargs));return {'observed':True}
        g=SimpleNamespace(client=SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create))))
        pace_gateway(g,30,clock=lambda:elapsed[0],sleep=sleep)
        for i in range(3):
            result=await g.client.chat.completions.create(model='synthetic-test-model',messages=[{'role':'user','content':str(i)}])
            assert result=={'observed':True}
        assert [t for t,_ in observed]==[0,30,60]
        assert observed[1][1]=={'model':'synthetic-test-model','messages':[{'role':'user','content':'1'}]}
        assert max(waits)<=25
    asyncio.run(run())
