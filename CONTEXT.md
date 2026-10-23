# Popcorn

Personal app for logging the movies I watch.

## Glossary

**Movie**
A film as described by The Movie Database (TMDB).

**Entry**
A movie I have added to my collection. Every entry has exactly one Status.
_Avoid:_ tracked movie, item

**Collection**
Every entry. To watch and Watched are the collection filtered by Status; Favourites is it filtered by Favourite.
_Avoid:_ tracking, library

**Drop**
Take a movie out of the collection. Its entry, with its Status, Watched date and Favourite, is lost.
_Avoid:_ untrack, remove, delete

**Status**
Either _To watch_ or _Watched_, never both. Marking a movie _Watched_ takes it off _To watch_. Unmarking _Watched_ drops the movie; it does not fall back to _To watch_. Rewatches are not recorded.
_Avoid:_ Watching (no longer a Status)

**Watched date**
The day a movie was marked _Watched_. Set automatically, not editable. For films seen long ago, it is the day they were logged.

**Favourite**
A mark on a watched movie meaning I liked it. Only watched movies can be favourites, so unmarking _Watched_ also clears the favourite. Favouriting an unwatched movie marks it _Watched_ too. Not a status.
_Avoid:_ like, liked

**Favourites**
The screen showing every favourite. A view, not a list movies are added to.

**Request**
A reel I shared to the app (from Instagram's Share button, or by pasting its link) to find out which movie or TV show it shows. Sharing the same reel again is the same Request. It is _in progress_ until the reel is read, then _found_, _not found_ or _failed_; a failed one can be retried. Signed out, a shared reel waits for sign-in and is dropped if I leave the app first.
_Avoid:_ scrape, job (those are the server's words for how a Request is worked on)
