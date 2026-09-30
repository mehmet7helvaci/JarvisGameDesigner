from game_designer.utils.logger import logger
from seeds.loader import load_all_seeds, load_seed_file

__all__ = ["load_all_seeds", "load_seed_file"]

if __name__ == "__main__":
    count = load_all_seeds()
    logger.info(f"Başarıyla {count} chunk yüklendi.")

