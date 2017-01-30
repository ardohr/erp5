/*global window, rJS*/
/*jslint nomen: true, maxlen:80, indent:2*/
var IMAGE = "data:image/png;base64,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";
(function (window, rJS) {
  "use strict";

  rJS(window)
    .ready(function (g) {
      g.props = {};
    })
    .ready(function (g) {
      return g.getElement()
        .push(function (element) {
          g.props.element = element;
        });
    })
    .declareMethod('render', function (options) {
      this.props.element.querySelector("center")
        .innerHTML =
        "<header>OfficeJS Installer</header>" +
        "<br>" +
        "<br>" +
        "<br>" +
        "<br>" +
        "<br>" +
        "<br>" +
        "<br>" +
        '<img width="100" height="100" title="" alt="" src="' + IMAGE + '" />' +
        "<br>" +
        '<div>Installing ' + options.app_name + '</div>' +
        "<br> We prepare your application for a 100 % offline mode" +
        '<div class="loader"></div>';
      return {};
    });

}(window, rJS));