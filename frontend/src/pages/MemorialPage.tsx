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
      className="font-medium text-accent hover:text-accent/80 hover:underline"
    >
      Digitize another cat
    </Link>
  );

  return (
    <div className="min-h-screen px-4 py-8 sm:py-10">
      <div className="mx-auto flex w-full max-w-3xl flex-col gap-6">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
          <h1 className="text-2xl sm:text-3xl font-bold text-text-primary">Memorial</h1>
          {digitizeLink}
        </div>

        {error && (
          <p
            role="alert"
            className="rounded-md border border-hp/50 bg-hp/10 px-4 py-3 text-sm text-hp"
          >
            {error}
          </p>
        )}

        {loading ? (
          <p role="status" className="flex items-center gap-2 text-text-secondary">
            <span className="inline-flex gap-1" aria-hidden="true">
              {[0, 1, 2].map((i) => (
                <motion.span
                  key={i}
                  className="inline-block h-2 w-2 bg-text-secondary"
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
          <div className="flex flex-col items-center gap-3 rounded-xl border border-border-ui bg-panel/40 px-6 py-12 text-center">
            <p className="text-lg text-text-secondary">No fallen cats yet.</p>
            <p className="text-sm text-text-disabled">
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
