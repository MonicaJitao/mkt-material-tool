import { NavLink } from 'react-router-dom';
import type { WorkflowStep } from '@/app/workflow';
import { StepperItem } from '@/components/Stepper/StepperItem';
import './stepper.css';

interface StepperProps {
  steps: WorkflowStep[];
  currentStep: string;
}

export function Stepper({ steps, currentStep }: StepperProps) {
  const currentIndex = steps.findIndex((step) => step.id === currentStep);

  return (
    <aside className="workflow-stepper" aria-label="任务阶段">
      <p className="workflow-stepper__title">阶段导航</p>
      <div className="workflow-stepper__list">
        {steps.map((step, index) => {
          const state = index < currentIndex ? 'done' : index === currentIndex ? 'active' : 'todo';

          return (
            <NavLink key={step.id} to={step.path} className="workflow-stepper__link">
              <StepperItem
                index={index + 1}
                label={step.label}
                hint={step.hint}
                state={state}
              />
            </NavLink>
          );
        })}
      </div>
    </aside>
  );
}
