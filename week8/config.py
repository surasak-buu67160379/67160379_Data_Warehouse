import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("pipeline")

@dataclass
class PipelineConfig:
    input_path: Path
    output_db: Path
    batches: list[str]
    error_mode: Literal["quarantine", "fail_fast"] = "quarantine"
    quarantine_csv: Path = Path("output/quarantine.csv")
    run_log_csv: Path = Path("output/pipeline_run_log.csv")

    def __post_init__(self):
        self.input_path = Path(self.input_path)
        self.output_db = Path(self.output_db)
        self.quarantine_csv = Path(self.quarantine_csv)
        self.run_log_csv = Path(self.run_log_csv)