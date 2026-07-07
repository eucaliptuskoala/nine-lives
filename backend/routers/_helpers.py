from fastapi import HTTPException, status


def load_game_run(supabase, run_id: str, user_id: str) -> dict:
    """Fetch the game_run, verifying it exists and is owned by the user.

    Raises 404 if the run does not exist, 403 if it belongs to another user,
    and 500 on unexpected DB failures.
    """
    try:
        result = supabase.table("game_run").select("*").eq("id", run_id).execute()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load game run: {exc}")

    if not result.data:
        raise HTTPException(status_code=404, detail="Game run not found.")

    game_run = result.data[0]

    if str(game_run.get("user_id")) != str(user_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not own this game run.",
        )

    return game_run
