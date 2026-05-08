import type { ReactNode } from 'react';
import type { WorkflowStep } from '@/app/workflow';
import { Header } from '@/components/Shell/Header';
import { Sidebar } from '@/components/Shell/Sidebar';
import { Stepper } from '@/components/Stepper/Stepper';
import './shell.css';

interface ShellProps {
  steps: WorkflowStep[];
  currentStep: string;
  children: ReactNode;
}

export function Shell({ steps, currentStep, children }: ShellProps) {
  return (
    <div className="shell-root">
      <Sidebar />
      <div className="shell-main">
        <Header />
        <div className="shell-workspace">
          <Stepper steps={steps} currentStep={currentStep} />
          <main className="shell-canvas">{children}</main>
        </div>
      </div>
    </div>
  );
}
