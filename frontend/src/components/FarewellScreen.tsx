import { motion } from "framer-motion";

interface FarewellScreenProps {
  catName: string;
  onGoToMemorial: () => void;
}

function FarewellScreen({ catName, onGoToMemorial }: FarewellScreenProps) {
  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 1 }}
      className="flex flex-col items-center justify-center min-h-screen bg-gray-900 text-white px-6 text-center"
    >
      <motion.p
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.5, duration: 0.6 }}
        className="text-6xl mb-6"
      >
        {"\uD83D\uDC94"}
      </motion.p>
      <motion.h1
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 0.8, duration: 0.5 }}
        className="text-2xl font-semibold mb-2"
      >
        {catName} has crossed the rainbow bridge
      </motion.h1>
      <motion.p
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 1.1, duration: 0.5 }}
        className="text-gray-400 mb-8 max-w-sm"
      >
        All nine lives spent with courage. They will be remembered.
      </motion.p>
      <motion.button
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ delay: 1.4, duration: 0.5 }}
        whileHover={{ scale: 1.03 }}
        whileTap={{ scale: 0.97 }}
        onClick={onGoToMemorial}
        className="px-6 py-3 rounded-lg bg-gray-700 hover:bg-gray-600 font-medium transition-colors"
      >
        Visit Memorial
      </motion.button>
    </motion.div>
  );
}

export default FarewellScreen;
