

# How to sync private packages
The `polymodel` dependency lives on private GCP Artifactory repository.  
In thoery, that should be access using `keyring` and `gcloud auth application-default login`,  
but that fails to authenticate. The [uv](https://docs.astral.sh/uv/guides/integration/alternative-indexes/#authenticate-with-a-google-access-token) itself suggests passing env variables directly, but that fails too.
Thus, a the only validated method to pull private packages is using
```
TOKEN="$(gcloud auth print-access-token)"
uv sync \
  --extra-index-url "https://oauth2accesstoken:${TOKEN}@{LOCATION}-python.pkg.dev/{PROJECT}/{REPO}/simple/"
``` 