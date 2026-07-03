import { Link } from "react-router-dom";
import { motion } from "framer-motion";
import { useMemorial } from "../hooks/useMemorial";
import MemorialCatCard from "../components/MemorialCatCard";

/**
 * MemorialPage — displays the authenticated user's fallen (MEMORIAL) cats.
 * Reads and updates data exclusively through the backend Data API via
 * `useMemorial` (no direct Supabase database access).
 */
function MemorialPage() {
  const { cats, loading, error, updateNote } = useMemorial();

  const digitizeLink = (
    <Link
      to="/"
      className="font-medium text-indigo-400 hover:text-indigo-300 hover:underline"
    >
      Digitize another cat
    </Link>
  );

  return (
    <div className="min-h-screen px-4 py-8 sm:py-10">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
          <h1 className="text-2xl sm:text-3xl font-bold text-white">Memorial</h1>
          {digitizeLink}
        </div>

        {error && (
          <p
            role="alert"
            className="rounded-md border border-red-500/50 bg-red-500/10 px-4 py-3 text-sm text-red-300"
          >
            {error}
          </p>
        )}

        {loading ? (
          <p role="status" className="flex items-center gap-2 text-gray-400">
            <span className="inline-flex gap-1" aria-hidden="true">
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  className="inline-block h-2 w-2 bg-gray-400"
                  animate={{ opacity: [0.2, 1, 0.2] }}
                  transition={{
                    duration: 0.9,
                    repeat: Infinity,
                    delay: i * 0.15,
                  }}
                />
              ))}
            </span>
            Loading fallen cats...
          </p>
        ) : cats.length === 0 ? (
          <div className="flex flex-col items-center gap-3 rounded-xl border border-gray-700 bg-gray-800/40 px-6 py-12 text-center">
            <p className="text-lg text-gray-300">No fallen cats yet.</p>
            <p className="text-sm text-gray-500">
              Cats that fall in battle will be remembered here.
            </p>
            {digitizeLink}
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            {cats.map((cat) => (
              <MemorialCatCard
                key={cat.id}
                cat={cat}
                onSaveNote={updateNote}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default MemorialPage;
