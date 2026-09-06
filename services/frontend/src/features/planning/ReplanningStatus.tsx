/**
 * Planning barrier feedback. The hourly replanning round is silent: it lasts a fraction of a
 * second and blocks the next step anyway, so a banner every hour only flickers. Only the two
 * states a person must know about are shown: the initial plan being built and a failed round.
 */
export function ReplanningStatus({ status, onRetry }: { status: 'idle' | 'planning' | 'replanning' | 'replan_failed'; onRetry: () => void }) {
  if (status === 'idle' || status === 'replanning') return null
  const failed = status === 'replan_failed'
  return <section className={'card planning-status ' + (failed ? 'planning-error' : '')} role={failed ? 'alert' : 'status'} aria-live={failed ? 'assertive' : 'polite'}>
    <strong>{failed ? 'Перепланирование не выполнено' : 'Строим план…'}</strong>
    {failed && <><p>Факты часа сохранены. Следующий час заблокирован до принятия того же раунда Planner.</p><button type="button" onClick={onRetry}>Повторить перепланирование</button></>}
  </section>
}
