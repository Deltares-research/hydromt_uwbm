import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from hydromt import hydromt_step
from hydromt.model.components import TablesComponent

if TYPE_CHECKING:
    from hydromt_uwbm.uwbm import UWBM

logger = logging.getLogger(__name__)


class UWBMForcingComponent(TablesComponent):
    """Component for handling Urban Water Balance Model (UWBM) forcing data."""

    _FORCING_COLUMN_ORDER = ["P_atm", "Ref.grass", "E_pot_OW"]

    model: "UWBM"

    @hydromt_step
    def read(self, filename: str | None = None, **kwargs) -> None:
        """Read forcing data from model folder in model ready format (.csv)."""
        self.root._assert_read_mode()
        path = Path(self.root.path, filename or self._filename)
        files = path.parent.glob(path.name)

        for path in files:
            df = pd.read_csv(path, sep=",", parse_dates=["date"], **kwargs)
            df = df.set_index("date")

            for col in df.columns:
                self.set(df[[col]], name=col)

    @hydromt_step
    def write(self, filename: str | None = None, **kwargs) -> None:
        """Write forcing data to model folder.

        Parameters
        ----------
        filename: str | None
            Filename to write to. If None, a default filename will be generated.
        **kwargs:
            Additional keyword arguments passed to pandas.DataFrame.to_csv().
        """
        self._write(
            start=self.model.config.get_value("starttime"),
            end=self.model.config.get_value("endtime"),
            timestep=self.model.config.get_value("timestep"),
            name=self.model.config.get_value("name"),
            filename=filename,
            decimals=self.model.config.get_value("output.decimals", fallback=3),
            **kwargs,
        )

    def _write(
        self,
        *,
        start: datetime,
        end: datetime,
        timestep: int,
        name: str,
        filename: str | None = None,
        decimals: int | None = None,
        **kwargs,
    ) -> None:
        """Write forcing data to model folder in model ready format (.csv)."""
        if len(self.data) > 0:
            self.root._assert_write_mode()
            logger.info("Writing forcing file")

            time_index = pd.date_range(
                start=start, end=end, freq=timedelta(seconds=timestep), name="date"
            )
            df = pd.concat(self.data.values(), axis=1)
            df = df.set_index(time_index)
            df.index.name = "date"

            if not all(col in df.columns for col in self._FORCING_COLUMN_ORDER):
                raise ValueError(
                    f"Not all required forcing columns found in data.\n"
                    f"Required columns are {self._FORCING_COLUMN_ORDER}\n"
                    f"Found columns are {df.columns.tolist()}"
                )
            df = df.loc[:, self._FORCING_COLUMN_ORDER]

            if decimals is not None:
                df = df.round(decimals)

            if filename is None:
                years = int((end - start).days / 365.25)
                h = int(timestep / 3600)
                filename = f"input/Forcing_{name}_{years}y_{h}h.csv"

            path = Path(self.root.path, filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            df.to_csv(path, sep=",", date_format="%d-%m-%Y %H:%M", **kwargs)
