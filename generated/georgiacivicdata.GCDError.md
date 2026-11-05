# georgiacivicdata.GCDError

### *exception* georgiacivicdata.GCDError(message, \*, code, status=None, details=None)

Base class of every error from the Georgia Civic Data API or this package.

* **Variables:**
  * **message** (*str*) -- The full message.
  * **code** (*str*) -- The API's error code (`"TOPIC_NOT_FOUND"`, `"UNSUPPORTED_FILTER"`,
    ...) or the package's own (`"PLACE_NOT_FOUND"`, `"NOT_A_DATASET"`,
    ...). Without an envelope, `"HTTP_<status>"`.
  * **status** (*int* *or* *None*) -- The HTTP status, or `None` when no HTTP response was involved.
  * **details** (*dict*) -- The error's details, such as `did_you_mean` suggestions.
