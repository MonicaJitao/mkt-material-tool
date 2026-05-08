type StepState = 'todo' | 'active' | 'done';

interface StepperItemProps {
  index: number;
  label: string;
  hint: string;
  state: StepState;
}

export function StepperItem({ index, label, hint, state }: StepperItemProps) {
  return (
    <article className={`stepper-item stepper-item--${state}`}>
      <div className="stepper-item__index">{state === 'done' ? '✓' : index}</div>
      <div className="stepper-item__body">
        <strong>{label}</strong>
        <p>{hint}</p>
      </div>
    </article>
  );
}
