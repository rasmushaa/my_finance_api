from pydantic import BaseModel
from fastapi import HTTPException
from typing import Dict, Any, List
import pandas as pd

CANONICAL_FEATURES = [
    "date",
    "receiver",
    "amount",
]

class PredictRequest(BaseModel):
    """A Pydantic model for the prediction request payload.
    
    Details
    -------
    This model expects a dictionary of input features required by the ML model.
    The `to_dataframe` method converts this dictionary into a pandas DataFrame
    with the specified columns needed for prediction.
    The payload may contain additional fields, which will be ignored.
    """
    inputs: Dict[str, List[Any]]

    def to_dataframe(self) -> pd.DataFrame:
        """Convert the input dictionary to a pandas DataFrame with with canonical columns.

        Input features are validated before conversion.

        Returns
        -------
        pd.DataFrame
            A DataFrame constructed from the input dictionary.
        """
        self.__validate_features()
        sorted_inputs = {col: self.inputs[col] for col in CANONICAL_FEATURES}
        df = pd.DataFrame.from_dict(sorted_inputs)
        return df
        
    def __validate_features(self) -> None:
        """Validate that all canonical features are present in the input."""
        missing = set(CANONICAL_FEATURES) - self.inputs.keys()
        extra = self.inputs.keys() - set(CANONICAL_FEATURES)
        if missing:
            raise HTTPException(status_code=400, detail=f"Missing required features: {missing}")
        if extra:
            raise HTTPException(status_code=400, detail=f"Unexpected features provided: {extra}")

class PredictResponse(BaseModel):
    predictions: List[str]
