!function(a){"function"==typeof define&&define.amd?define(["jquery"],a):a(jQuery)}(function(a){"use_strict";function b(a,b){c(a).find(".tag-name").each(function(){c(this).click(function(){var a=c(this).text(),d=a.split(":");return b(d[0],d[1]),!0})})}var c=a;return a.fn.autocomplete_tagging=function(d){function e(a){c(a).mouseenter(function(){c(this).attr("src",h.delete_tag_img_rollover)}),c(a).mouseleave(function(){c(this).attr("src",h.delete_tag_img)}),c(a).click(function(){var b=c(this).parent(),d=b.find(".tag-name").eq(0),e=d.text(),f=e.split(":"),g=f[0],i=f[1],l=b.prev();b.remove(),delete h.tags[g];var m=h.get_toggle_link_text_fn(h.tags);return k.text(m),c.ajax({url:h.ajax_delete_tag_url,data:{tag_name:g},error:function(){h.tags[g]=i,l.hasClass("tag-button")?l.after(b):j.prepend(b),alert("Remove tag failed"),k.text(h.get_toggle_link_text_fn(h.tags)),a.mouseenter(function(){c(this).attr("src",h.delete_tag_img_rollover)}),a.mouseleave(function(){c(this).attr("src",h.delete_tag_img)})},success:function(){}}),!0})}function f(a){var b=c("<img/>").attr("src",h.delete_tag_img).addClass("delete-tag-img");e(b);var d=c("<span>").text(a).addClass("tag-name");d.click(function(){var b=a.split(":");return h.tag_click_fn(b[0],b[1]),!0});var f=c("<span></span>").addClass("tag-button");return f.append(d),h.editable&&f.append(b),f}var g={get_toggle_link_text_fn:function(a){var b="",c=_.size(a);return b=c>0?c+(c>1?" Tags":" Tag"):"Add tags"},tag_click_fn:function(){},editable:!0,input_size:20,in_form:!1,tags:{},use_toggle_link:!0,item_id:"",add_tag_img:"",add_tag_img_rollover:"",delete_tag_img:"",ajax_autocomplete_tag_url:"",ajax_retag_url:"",ajax_delete_tag_url:"",ajax_add_tag_url:""},h=a.extend(g,d),i=c(this),j=i.find(".tag-area"),k=i.find(".toggle-link"),l=i.find(".tag-input"),m=i.find(".add-tag-button");k.click(function(){var a;return a=j.is(":hidden")?function(){var a=c(this).find(".tag-button").length;0===a&&j.click()}:function(){j.blur()},j.slideToggle("fast",a),c(this)}),h.editable&&l.hide(),l.keyup(function(a){if(27===a.keyCode)c(this).trigger("blur");else if(13===a.keyCode||188===a.keyCode||32===a.keyCode){var b=this.value;if(-1!==b.indexOf(": ",b.length-2))return this.value=b.substring(0,b.length-1),!1;if((188===a.keyCode||32===a.keyCode)&&(b=b.substring(0,b.length-1)),b=c.trim(b),b.length<2)return!1;this.value="";var d=f(b),e=j.children(".tag-button");if(0!==e.length){var g=e.slice(e.length-1);g.after(d)}else j.prepend(d);var i=b.split(":");h.tags[i[0]]=i[1];var l=h.get_toggle_link_text_fn(h.tags);k.text(l);var m=c(this);return c.ajax({url:h.ajax_add_tag_url,data:{new_tag:b},error:function(){d.remove(),delete h.tags[i[0]];var a=h.get_toggle_link_text_fn(h.tags);k.text(a),alert("Add tag failed")},success:function(){m.data("autocompleter").cacheFlush()}}),!1}});var n=function(a,b,c,d){var e=d.split(":");return 1===e.length?e[0]:e[1]},o={selectFirst:!1,formatItem:n,autoFill:!1,highlight:!1};l.autocomplete(h.ajax_autocomplete_tag_url,o),i.find(".delete-tag-img").each(function(){e(c(this))}),b(c(this),h.tag_click_fn),m.click(function(){return c(this).hide(),j.click(),!1}),h.editable&&(j.bind("blur",function(){_.size(h.tags)>0&&(m.show(),l.hide(),j.removeClass("active-tag-area"))}),j.click(function(a){var b=c(this).hasClass("active-tag-area");if(c(a.target).hasClass("delete-tag-img")&&!b)return!1;if(c(a.target).hasClass("tag-name")&&!b)return!1;c(this).addClass("active-tag-area"),m.hide(),l.show(),l.focus();var d=function(a){var b=function(a,b){a.attr("id");b!==a&&(a.blur(),c(window).unbind("click.tagging_blur"),c(this).addClass("agenttip"))};b(j,c(a.target))};return c(window).bind("click.tagging_blur",d),!1})),h.use_toggle_link&&j.hide()},b});
//# sourceMappingURL=../../maps/ui/autocom_tagging.js.map