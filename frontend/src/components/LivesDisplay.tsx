import { motion } from "framer-motion";

interface LivesDisplayProps {
  lives: number;
}

const TOTAL_LIVES = 9;

function LivesDisplay({ lives }: LivesDisplayProps) {
  return (
    <div className="flex gap-0.5">
      {Array.from({ length: TOTAL_LIVES }).map((_, i) => (
        <motion.span
          key={i}
          className={`text-lg ${i < lives ? "text-red-400" : "text-gray-700"}`}
          animate={i === lives ? { scale: [1, 1.3, 1] } : {}}
          transition={{ duration: 0.4 }}
        >
          {i < lives ? "\u2764" : "\u2661"}
        </motion.span>
      ))}
    </div>
  );
}

export default LivesDisplay;
