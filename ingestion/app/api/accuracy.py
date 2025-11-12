from fastapi import APIRouter

router = APIRouter()

@router.get("/test")
async def test_accuracy_endpoint():
    """Endpoint di test per verificare che il modulo sia caricato"""
    return {"success": True, "message": "Accuracy module loaded successfully"}
