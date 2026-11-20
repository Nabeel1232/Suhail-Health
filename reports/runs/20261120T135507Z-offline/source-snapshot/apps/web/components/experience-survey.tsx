'use client';

import {rows, type CareCase, type Row} from '@/lib/api';
import {ActionForm, Field, Panel} from './ui';
import {Icon} from './icon';

type SurveyProps = {
  c: CareCase;
  language: 'en' | 'ar';
  command: (path: string, body: Row) => Promise<unknown>;
};

export function ExperienceSurvey({c, language, command}: SurveyProps) {
  const ar = language === 'ar';
  const latest = rows(c.experience).at(-1);
  const ratings = (low: string, high: string) => [
    {value: '', label: ar ? 'اختر تقييماً' : 'Choose a rating'},
    ...[1, 2, 3, 4, 5].map(value => ({
      value: String(value),
      label: `${value}${value === 1 ? ` — ${low}` : value === 5 ? ` — ${high}` : ''}`,
    })),
  ];

  return <Panel title={ar ? 'كيف تبدو لك الخطوة التالية؟' : 'How does the next step feel?'} className="pt-survey" eyebrow={ar ? 'تجربتك مهمة' : 'YOUR EXPERIENCE MATTERS'} action={<span className="pt-panel-symbol"><Icon name="heart" size={19}/></span>}>
    <p className="panel-intro">{ar ? 'ملاحظات اختيارية تساعد فريقك على فهم تجربتك. لا تغيّر هذه الإجابات خطتك الطبية، ولا تمثل تحسناً صحياً مثبتاً.' : 'Optional feedback helps your team understand your experience. These answers do not change your clinical plan or establish a health improvement.'}</p>
    <ActionForm label={ar ? 'إرسال الملاحظات الاختيارية' : 'Share optional feedback'} onSubmit={data => command(`/cases/${c.id}/experience`, {
      confidence: Number(data.confidence),
      reassurance: Number(data.reassurance),
    })}>
      <Field name="confidence" label={ar ? 'ما مدى وضوح الخطوة التالية بالنسبة لك؟' : 'How clear is your next step?'} options={ratings(ar ? 'غير واضح' : 'Not clear', ar ? 'واضح جداً' : 'Very clear')}/>
      <Field name="reassurance" label={ar ? 'إلى أي مدى تشعر بالاطمئنان بشأن الحصول على مساعدة للخطوة التالية؟' : 'How reassured do you feel about getting help with your next step?'} options={ratings(ar ? 'غير مطمئن' : 'Not reassured', ar ? 'مطمئن جداً' : 'Very reassured')}/>
    </ActionForm>
    {latest && <div className="pt-feedback-record">
      <p className="microcopy"><Icon name="check-circle" size={14}/>{ar ? 'آخر ملاحظات مسجّلة' : 'Latest recorded feedback'}</p>
      <div><span>{ar ? 'الوضوح' : 'Clarity'}</span><strong>{latest.confidence}<small>/5</small></strong></div>
      <div><span>{ar ? 'الاطمئنان' : 'Reassurance'}</span><strong>{latest.reassurance}<small>/5</small></strong></div>
    </div>}
  </Panel>;
}
