import { useParams, Link } from "react-router-dom";

function BattlePage() {
  const { runId } = useParams<{ runId: string }>();

  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-4">
      <h1 className="text-3xl font-bold">Battle</h1>
      <p className="text-gray-500">Run: {runId}</p>
      <Link to="/memorial" className="text-blue-500 underline">
        View Memorial
      </Link>
    </div>
  );
}

export default BattlePage;
