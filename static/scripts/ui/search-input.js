!function(a){"function"==typeof define&&define.amd?define([],a):a(jQuery)}(function(){function a(a,c){function d(){var a=$(this).parent().children("input");a.focus().val("").trigger("clear:searchInput"),c.onclear()}function e(a,b){$(this).trigger("search:searchInput",b),"function"==typeof c.onfirstsearch&&n?(n=!1,c.onfirstsearch(b)):c.onsearch(b)}function f(){return['<input type="text" name="',c.name,'" placeholder="',c.placeholder,'" ','class="search-query ',c.classes,'" ',"/>"].join("")}function g(){return $(f()).focus(function(){$(this).select()}).keyup(function(a){if(a.preventDefault(),a.stopPropagation(),$(this).val()||$(this).blur(),a.which===k&&c.escWillClear)d.call(this,a);else{var b=$(this).val();a.which===l||c.minSearchLen&&b.length>=c.minSearchLen?e.call(this,a,b):b.length||d.call(this,a)}}).on("change",function(a){e.call(this,a,$(this).val())}).val(c.initialVal)}function h(){return $(['<span class="search-clear fa fa-times-circle" ','title="',b("clear search (esc)"),'"></span>'].join("")).agenttip({placement:"bottom"}).click(function(a){d.call(this,a)})}function i(){return $(['<span class="search-loading fa fa-spinner fa-spin" ','title="',b("loading..."),'"></span>'].join("")).hide().agenttip({placement:"bottom"})}function j(){m.find(".search-loading").toggle(),m.find(".search-clear").toggle()}var k=27,l=13,m=$(a),n=!0,o={initialVal:"",name:"search",placeholder:"search",classes:"",onclear:function(){},onfirstsearch:null,onsearch:function(){},minSearchLen:0,escWillClear:!0,oninit:function(){}};return"string"===jQuery.type(c)?("toggle-loading"===c&&j(),m):("object"===jQuery.type(c)&&(c=jQuery.extend(!0,{},o,c)),m.addClass("search-input").prepend([g(),h(),i()]))}var b=window._l||function(a){return a};jQuery.fn.extend({searchInput:function(b){return this.each(function(){return a(this,b)})}})});
//# sourceMappingURL=../../maps/ui/search-input.js.map