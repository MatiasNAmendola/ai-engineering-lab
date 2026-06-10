from .seed_nem_fase2 import seed_nem_fase2
from .seed_nem_fase3 import seed_nem_fase3
from .seed_nem_fase4 import seed_nem_fase4
from .seed_nem_fase5 import seed_nem_fase5
from .seed_nem_fase6 import seed_nem_fase6


def seed_all_fases(nem_repo):
    results = {}
    results["fase2"] = seed_nem_fase2(nem_repo)
    results["fase3"] = seed_nem_fase3(nem_repo)
    results["fase4"] = seed_nem_fase4(nem_repo)
    results["fase5"] = seed_nem_fase5(nem_repo)
    results["fase6"] = seed_nem_fase6(nem_repo)
    return results
