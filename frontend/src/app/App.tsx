import { Outlet, useLocation } from 'react-router-dom';
import { Shell } from '@/components/Shell/Shell';
import { workflowSteps } from '@/app/workflow';

function resolveCurrentStep(pathname: string): string {
  const matched = workflowSteps.find((step) => pathname.startsWith(step.path));
  return matched?.id ?? workflowSteps[0].id;
}

export default function App() {
  const location = useLocation();
  const currentStep = resolveCurrentStep(location.pathname);

  return (
    <Shell steps={workflowSteps} currentStep={currentStep}>
      <Outlet />
    </Shell>
  );
}
