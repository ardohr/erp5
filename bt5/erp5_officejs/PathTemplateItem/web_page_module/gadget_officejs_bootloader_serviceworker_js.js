/*jslint indent: 2*/
/*global self, fetch, Request, Response, console */
var global = self, window = self;

(function (self, fetch, Request, Response, console) {
  "use strict";

  self.DOMParser = {};
  self.sessionStorage = {};
  self.localStorage = {};
  self.openDatabase = {};
  self.DOMError = {};
  self.postMessage = function () {return; };

  self.importScripts('rsvp.js', 'jiodev.js');

  self.storage = {};

  function createStorage(database) {
    return self.jIO.createJIO({
      type: "uuid",
      sub_storage: {
        type: "indexeddb",
        database: database
      }
    });
  }

  self.addEventListener("message", function (event) {

    event.waitUntil(new self.RSVP.Queue()
      .push(function () {
        var data = JSON.parse(event.data);

        if (data.action === "install" &&
            data.url_list !== undefined) {

          self.storage = createStorage(self.registration.scope);
          return new self.RSVP.Queue()
            .push(function () {
              var promise_list = [];
              data.url_list.map(function (url) {
                promise_list.push(
                  new self.RSVP.Queue()
                    .push(function () {
                      return self.storage.get(url);
                    })
                    .push(undefined, function () {
                      return new self.RSVP.Queue()
                        .push(function () {
                          return fetch(new Request(url));
                        })
                        .push(function (response) {
                          if (response.status === 200) {
                            return self.RSVP.all([
                              self.storage.put(
                                url,
                                {"content_type": "blob"}
                              ),
                              response.blob()
                            ]);
                          }
                          throw new Error(response.statusText);
                        })
                        .push(function (result) {
                          return self.storage.putAttachment(
                            url,
                            "body",
                            result[1]
                          );
                        })
                        .push(function () {
                          console.log("Saved: ", url);
                        })
                        .push(undefined, function (error) {
                          console.log(
                            "error on",
                            url,
                            "cause: ",
                            error.message
                          );
                        });
                    })
                );
              });
              return self.RSVP.all(promise_list);
            })
            .push(function () {
              event.ports[0].postMessage("success");
            });
        }
      }));
  });

  self.addEventListener("fetch", function (event) {
    var relative_url = event.request.url.replace(self.registration.scope, "")
      .replace(self.version_url, "");
    if (relative_url === "") {
      relative_url = "/";
    }

    event.respondWith(
      new self.RSVP.Queue()
        .push(function () {
          if (self.storage.get === undefined) {
            self.storage = createStorage(self.registration.scope);
          }
          return self.storage.get(relative_url);
        })
        .push(function (doc) {
          if (doc.content_type !== "blob") {
            return new Response(doc.text_content, {
              'headers': {
                'content-type': doc.content_type
              }
            });
          }
          return self.storage.getAttachment(relative_url, "body")
            .push(function (blob) {
              return new Response(blob, {
                'headers': {
                  'content-type': blob.type
                }
              });
            });
        })
        .push(undefined, function (error) {
          console.log(
            "Relative_Url: ",
            relative_url,
            "\nCause: ",
            error.message
          );
          return fetch(event.request);
        })
    );
  });

}(self, fetch, Request, Response, console));