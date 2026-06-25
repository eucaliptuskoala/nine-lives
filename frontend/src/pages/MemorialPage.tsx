import { Link } from "react-router-dom";

function MemorialPage() {
  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-4">
      <h1 className="text-3xl font-bold">Memorial</h1>
      <p className="text-gray-500">Fallen cats rest here.</p>
      <Link to="/" className="text-blue-500 underline">
        Digitize another cat
      </Link>
    </div>
  );
}

export default MemorialPage;
