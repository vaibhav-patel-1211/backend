"""
Gives the model a short note about the user's tradition so its answers lean the
right way (a Catholic asking about the Eucharist shouldn't get a Protestant
take). We support three traditions and quietly default to Protestant for
anything we don't recognise.
"""
from app.config import settings

# One sentence of guidance per tradition, glued into the system prompt.
_CONTEXT = {
    "Catholic": (
        "The user follows the Catholic tradition. Consider Sacred Tradition and the "
        "Magisterium alongside scripture, the seven sacraments, and the role of the "
        "saints and the Church Fathers where relevant."
    ),
    "Protestant": (
        "The user follows the Protestant tradition. Emphasize sola scriptura and "
        "salvation by grace through faith, while remaining fair to other views."
    ),
    "Orthodox": (
        "The user follows the Eastern Orthodox tradition. Consider Holy Tradition, the "
        "ecumenical councils, theosis, and the writings of the Church Fathers where relevant."
    ),
}


def normalize(denomination: str) -> str:
    """Tidy up whatever was sent into one of our three names (default Protestant)."""
    if not denomination:
        return "Protestant"
    for d in settings.DENOMINATIONS:
        if d.lower() == denomination.strip().lower():
            return d
    return "Protestant"


def get_context(denomination: str) -> str:
    """The guidance sentence for a tradition, ready to drop into the prompt."""
    return _CONTEXT.get(normalize(denomination), _CONTEXT["Protestant"])
