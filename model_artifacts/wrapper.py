import joblib
import mlflow.models
import mlflow.pyfunc
import pandas as pd


class ModelWrapper(mlflow.pyfunc.PythonModel):
    """MLflow model wrapper to save and load model with preprocessors.

    This is the main class used by MLflow to save and load the model along with its
    preprocessing steps. It applies the preprocessors in sequence before making predictions
    with the trained model.
    """

    def load_context(self, context):
        """Load model and preprocessors from artifacts.

        Inputs:
        context: dict
            MLflow model context with artifacts paths.
        """
        self.__pipeline = joblib.load(context.artifacts["pipeline"])

    def predict(self, context, model_input: pd.DataFrame):
        """Apply preprocessors and model to input data.

        Inputs:
        context: dict
            MLflow model context with artifacts paths.
        model_input: pd.DataFrame
            Input data for prediction.

        Returns:
        pd.DataFrame or np.ndarray
            Model predictions.
        """
        return self.__pipeline.predict(model_input)


# Set this as the model for MLflow when loaded as code
mlflow.models.set_model(ModelWrapper())
