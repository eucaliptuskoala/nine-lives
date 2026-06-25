import { useState, useEffect } from "react";
import type { Cat } from "../types/game";
import { CatStatus } from "../types/game";
import { supabase } from "./useSupabase";

export function useMemorial() {
  const [cats, setCats] = useState<Cat[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMemorial = async () => {
      const { data } = await supabase
        .from("cat")
        .select("*")
        .eq("status", CatStatus.MEMORIAL)
        .order("death_date", { ascending: false });

      if (data) setCats(data as Cat[]);
      setLoading(false);
    };

    fetchMemorial();
  }, []);

  return { cats, loading };
}
