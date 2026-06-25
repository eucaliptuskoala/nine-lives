from fastapi import APIRouter, UploadFile, File

router = APIRouter(prefix="/digitize", tags=["digitize"])


@router.post("")
async def digitize_cat(file: UploadFile = File(...)):
    pass
