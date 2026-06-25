const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function uploadCatPhoto(file: File) {
  const form = new FormData();
  form.append("file", file);

  const res = await fetch(`${API_BASE}/api/digitize`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) throw new Error("Digitization failed");
  return res.json();
}
