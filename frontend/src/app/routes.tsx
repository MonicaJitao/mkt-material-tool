import { Navigate, createBrowserRouter } from 'react-router-dom';
import App from '@/app/App';
import { BriefPage } from '@/pages/BriefPage';
import { PlanReviewPage } from '@/pages/PlanReviewPage';
import { ImageBatchPage } from '@/pages/ImageBatchPage';
import { HtmlGeneratePage } from '@/pages/HtmlGeneratePage';
import { HtmlEditorPage } from '@/pages/HtmlEditorPage';
import { LibraryPage } from '@/pages/LibraryPage';

export const appRouter = createBrowserRouter([
  {
    path: '/',
    element: <App />,
    children: [
      { index: true, element: <Navigate to="/brief" replace /> },
      { path: 'brief', element: <BriefPage /> },
      { path: 'plan-review', element: <PlanReviewPage /> },
      { path: 'image-batch', element: <ImageBatchPage /> },
      { path: 'html-generate', element: <HtmlGeneratePage /> },
      { path: 'html-editor', element: <HtmlEditorPage /> },
      { path: 'library', element: <LibraryPage /> },
    ],
  },
]);
