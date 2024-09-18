function init_galaxy_elts(a){$(".annotation",a._doc.body).each(function(){$(this).click(function(){var b=a._doc.createRange();b.selectNodeContents(this);var c=window.getSelection();c.removeAllRanges(),c.addRange(b)})})}function get_item_info(a){var b,c,d;switch(a){case CONTROLS.ITEM_HISTORY:b="History",c="Histories",d="history",item_class="History";break;case CONTROLS.ITEM_DATASET:b="Dataset",c="Datasets",d="dataset",item_class="HistoryDatasetAssociation";break;case CONTROLS.ITEM_WORKFLOW:b="Workflow",c="Workflows",d="workflow",item_class="StoredWorkflow";break;case CONTROLS.ITEM_PAGE:b="Page",c="Pages",d="page",item_class="Page";break;case CONTROLS.ITEM_VISUALIZATION:b="Visualization",c="Visualizations",d="visualization",item_class="Visualization"}var e="list_"+c.toLowerCase()+"_for_selection",f=list_objects_url.replace("LIST_ACTION",e);return{singular:b,plural:c,controller:d,iclass:item_class,list_ajax_url:f}}function make_item_importable(a,b,c){ajax_url=set_accessible_url.replace("ITEM_CONTROLLER",a),$.ajax({type:"POST",url:ajax_url,data:{id:b,accessible:"True"},error:function(){alert("Making "+c+" accessible failed")}})}var CONTROLS={ITEM_HISTORY:"item_history",ITEM_DATASET:"item_dataset",ITEM_WORKFLOW:"item_workflow",ITEM_PAGE:"item_page",ITEM_VISUALIZATION:"item_visualization",DIALOG_HISTORY_LINK:"link_history",DIALOG_DATASET_LINK:"link_dataset",DIALOG_WORKFLOW_LINK:"link_workflow",DIALOG_PAGE_LINK:"link_page",DIALOG_VISUALIZATION_LINK:"link_visualization",DIALOG_EMBED_HISTORY:"embed_history",DIALOG_EMBED_DATASET:"embed_dataset",DIALOG_EMBED_WORKFLOW:"embed_workflow",DIALOG_EMBED_PAGE:"embed_page",DIALOG_EMBED_VISUALIZATION:"embed_visualization"};WYMeditor.editor.prototype.dialog=function(a){function b(){$("#set_link_id").click(function(){$("#link_attribute_label").text("ID/Name");var a=$(".wym_href");a.addClass("wym_id").removeClass("wym_href"),e&&a.val($(e).attr("id")),$(this).remove()})}var c=this,d=c.uniqueStamp(),e=c.selected();if(a==WYMeditor.DIALOG_LINK){e&&($(c._options.hrefSelector).val($(e).attr(WYMeditor.HREF)),$(c._options.srcSelector).val($(e).attr(WYMeditor.SRC)),$(c._options.titleSelector).val($(e).attr(WYMeditor.TITLE)),$(c._options.altSelector).val($(e).attr(WYMeditor.ALT)));var f,g;e&&(f=$(e).attr("href"),void 0==f&&(f=""),g=$(e).attr("title"),void 0==g&&(g="")),show_modal("Create Link","<div><div><label id='link_attribute_label'>URL <span style='float: right; font-size: 90%'><a href='#' id='set_link_id'>Create in-page anchor</a></span></label><br><input type='text' class='wym_href' value='"+f+"' size='40' /></div><div><label>Title</label><br><input type='text' class='wym_title' value='"+g+"' size='40' /></div><div>",{"Make link":function(){var a=$(c._options.hrefSelector).val()||"",b=$(".wym_id").val()||"",e=$(c._options.titleSelector).val()||"";if(a||b){c._exec(WYMeditor.CREATE_LINK,d);var f=$("a[href="+d+"]",c._doc.body);f.attr(WYMeditor.HREF,a).attr(WYMeditor.TITLE,e).attr("id",b),0===f.text().indexOf("wym-")&&f.text(e)}hide_modal()},Cancel:function(){hide_modal()}},{},b)}if(a==WYMeditor.DIALOG_IMAGE)return c._selected_image&&($(c._options.dialogImageSelector+" "+c._options.srcSelector).val($(c._selected_image).attr(WYMeditor.SRC)),$(c._options.dialogImageSelector+" "+c._options.titleSelector).val($(c._selected_image).attr(WYMeditor.TITLE)),$(c._options.dialogImageSelector+" "+c._options.altSelector).val($(c._selected_image).attr(WYMeditor.ALT))),void show_modal("Image","<div class='row'><label>URL</label><br><input type='text' class='wym_src' value='' size='40' /></div><div class='row'><label>Alt text</label><br><input type='text' class='wym_alt' value='' size='40' /></div><div class='row'><label>Title</label><br><input type='text' class='wym_title' value='' size='40' /></div>",{Insert:function(){var a=$(c._options.srcSelector).val();a.length>0&&(c._exec(WYMeditor.INSERT_IMAGE,d),$("img[src$="+d+"]",c._doc.body).attr(WYMeditor.SRC,a).attr(WYMeditor.TITLE,$(c._options.titleSelector).val()).attr(WYMeditor.ALT,$(c._options.altSelector).val())),hide_modal()},Cancel:function(){hide_modal()}});if(a==WYMeditor.DIALOG_TABLE&&show_modal("Table","<div class='row'><label>Caption</label><br><input type='text' class='wym_caption' value='' size='40' /></div><div class='row'><label>Summary</label><br><input type='text' class='wym_summary' value='' size='40' /></div><div class='row'><label>Number Of Rows<br></label><input type='text' class='wym_rows' value='3' size='3' /></div><div class='row'><label>Number Of Cols<br></label><input type='text' class='wym_cols' value='2' size='3' /></div>",{Insert:function(){var a=$(c._options.rowsSelector).val(),b=$(c._options.colsSelector).val();if(a>0&&b>0){var d=c._doc.createElement(WYMeditor.TABLE),e=null,f=$(c._options.captionSelector).val(),g=d.createCaption();for(g.innerHTML=f,x=0;x<a;x++)for(e=d.insertRow(x),y=0;y<b;y++)e.insertCell(y);$(d).attr("summary",$(c._options.summarySelector).val());var h=$(c.findUp(c.container(),WYMeditor.MAIN_CONTAINERS)).get(0);h&&h.parentNode?$(h).after(d):$(c._doc.body).append(d)}hide_modal()},Cancel:function(){hide_modal()}}),a==CONTROLS.DIALOG_HISTORY_LINK||a==CONTROLS.DIALOG_DATASET_LINK||a==CONTROLS.DIALOG_WORKFLOW_LINK||a==CONTROLS.DIALOG_PAGE_LINK||a==CONTROLS.DIALOG_VISUALIZATION_LINK){var h;switch(a){case CONTROLS.DIALOG_HISTORY_LINK:h=get_item_info(CONTROLS.ITEM_HISTORY);break;case CONTROLS.DIALOG_DATASET_LINK:h=get_item_info(CONTROLS.ITEM_DATASET);break;case CONTROLS.DIALOG_WORKFLOW_LINK:h=get_item_info(CONTROLS.ITEM_WORKFLOW);break;case CONTROLS.DIALOG_PAGE_LINK:h=get_item_info(CONTROLS.ITEM_PAGE);break;case CONTROLS.DIALOG_VISUALIZATION_LINK:h=get_item_info(CONTROLS.ITEM_VISUALIZATION)}$.ajax({url:h.list_ajax_url,data:{},error:function(){alert("Failed to list "+h.plural.toLowerCase()+" for selection")},success:function(a){show_modal("Insert Link to "+h.singular,a+"<div><input id='make-importable' type='checkbox' checked/>Make the selected "+h.plural.toLowerCase()+" accessible so that they can viewed by everyone.</div>",{Insert:function(){var a=!1;null!==$("#make-importable:checked").val()&&(a=!0);new Array;$("input[name=id]:checked").each(function(){var b=$(this).val();a&&make_item_importable(h.controller,b,h.singular),url_template=get_name_and_link_url+b,ajax_url=url_template.replace("ITEM_CONTROLLER",h.controller),$.getJSON(ajax_url,function(a){c._exec(WYMeditor.CREATE_LINK,d);var e=$("a[href="+d+"]",c._doc.body).text();""==e||e==d?c.insert("<a href='"+a.link+"'>"+h.singular+" '"+a.name+"'</a>"):$("a[href="+d+"]",c._doc.body).attr(WYMeditor.HREF,a.link).attr(WYMeditor.TITLE,h.singular+b)})}),hide_modal()},Cancel:function(){hide_modal()}})}})}if(a==CONTROLS.DIALOG_EMBED_HISTORY||a==CONTROLS.DIALOG_EMBED_DATASET||a==CONTROLS.DIALOG_EMBED_WORKFLOW||a==CONTROLS.DIALOG_EMBED_PAGE||a==CONTROLS.DIALOG_EMBED_VISUALIZATION){var h;switch(a){case CONTROLS.DIALOG_EMBED_HISTORY:h=get_item_info(CONTROLS.ITEM_HISTORY);break;case CONTROLS.DIALOG_EMBED_DATASET:h=get_item_info(CONTROLS.ITEM_DATASET);break;case CONTROLS.DIALOG_EMBED_WORKFLOW:h=get_item_info(CONTROLS.ITEM_WORKFLOW);break;case CONTROLS.DIALOG_EMBED_PAGE:h=get_item_info(CONTROLS.ITEM_PAGE);break;case CONTROLS.DIALOG_EMBED_VISUALIZATION:h=get_item_info(CONTROLS.ITEM_VISUALIZATION)}$.ajax({url:h.list_ajax_url,data:{},error:function(){alert("Failed to list "+h.plural.toLowerCase()+" for selection")},success:function(b){(a==CONTROLS.DIALOG_EMBED_HISTORY||a==CONTROLS.DIALOG_EMBED_WORKFLOW||a==CONTROLS.DIALOG_EMBED_VISUALIZATION)&&(b=b+"<div><input id='make-importable' type='checkbox' checked/>Make the selected "+h.plural.toLowerCase()+" accessible so that they can viewed by everyone.</div>"),show_modal("Embed "+h.plural,b,{Embed:function(){var a=!1;null!=$("#make-importable:checked").val()&&(a=!0),$("input[name=id]:checked").each(function(){var b=$(this).val(),d=$("label[for='"+b+"']:first").text();a&&make_item_importable(h.controller,b,h.singular);var e=h.iclass+"-"+b,f=["<div id='",e,"' class='embedded-item ",h.singular.toLowerCase()," placeholder'>","<p class='title'>","Embedded Galaxy ",h.singular," '",d,"'","</p>","<p class='content'>","[Do not edit this block; Galaxy will fill it in with the annotated ",h.singular.toLowerCase()," when it is displayed.]","</p>","</div>"].join("");c.insert(f)}),hide_modal()},Cancel:function(){hide_modal()}})}})}},$(function(){$(document).ajaxError(function(a,b){var c=b.responseText||b.statusText||"Could not connect to server";return show_modal("Server error",c,{"Ignore error":hide_modal}),!1}),$("[name=page_content]").wymeditor({skin:"galaxy",basePath:editor_base_path,iframeBasePath:iframe_base_path,boxHtml:"<table class='wym_box' width='100%' height='100%'><tr><td><div class='wym_area_top'>"+WYMeditor.TOOLS+"</div></td></tr><tr height='100%'><td><div class='wym_area_main' style='height: 100%;'>"+WYMeditor.IFRAME+WYMeditor.STATUS+"</div></div></td></tr></table>",agentsItems:[{name:"Bold",title:"Strong",css:"wym_agents_strong"},{name:"Italic",title:"Emphasis",css:"wym_agents_emphasis"},{name:"Superscript",title:"Superscript",css:"wym_agents_superscript"},{name:"Subscript",title:"Subscript",css:"wym_agents_subscript"},{name:"InsertOrderedList",title:"Ordered_List",css:"wym_agents_ordered_list"},{name:"InsertUnorderedList",title:"Unordered_List",css:"wym_agents_unordered_list"},{name:"Indent",title:"Indent",css:"wym_agents_indent"},{name:"Outdent",title:"Outdent",css:"wym_agents_outdent"},{name:"Undo",title:"Undo",css:"wym_agents_undo"},{name:"Redo",title:"Redo",css:"wym_agents_redo"},{name:"CreateLink",title:"Link",css:"wym_agents_link"},{name:"Unlink",title:"Unlink",css:"wym_agents_unlink"},{name:"InsertImage",title:"Image",css:"wym_agents_image"},{name:"InsertTable",title:"Table",css:"wym_agents_table"}]});var a=$.wymeditors(0),b=function(b){show_modal("Saving page","progress"),$.ajax({url:save_url,type:"POST",data:{id:page_id,content:a.xhtml(),annotations:JSON.stringify(new Object),_:"true"},success:function(){b()}})};$("#save-button").click(function(){b(function(){hide_modal()})}),$("#close-button").click(function(){var a=!1;if(a){var c=function(){window.onbeforeunload=void 0,window.document.location=page_list_url};show_modal("Close editor","There are unsaved changes to your page which will be lost.",{Cancel:hide_modal,"Save Changes":function(){b(c)}},{"Don't Save":c})}else window.document.location=page_list_url});var c=$("<div class='galaxy-page-editor-button'><a id='insert-galaxy-link' class='action-button popup' href='#'>Paragraph type</a></div>");$(".wym_area_top").append(c);var d={};$.each(a._options.containersItems,function(b,c){var e=c.name;d[c.title.replace("_"," ")]=function(){a.container(e)}}),make_popupmenu(c,d);var e=$("<div><a id='insert-galaxy-link' class='action-button popup' href='#'>Insert Link to Galaxy Object</a></div>").addClass("galaxy-page-editor-button");$(".wym_area_top").append(e),make_popupmenu(e,{"Insert History Link":function(){a.dialog(CONTROLS.DIALOG_HISTORY_LINK)},"Insert Dataset Link":function(){a.dialog(CONTROLS.DIALOG_DATASET_LINK)},"Insert Workflow Link":function(){a.dialog(CONTROLS.DIALOG_WORKFLOW_LINK)},"Insert Page Link":function(){a.dialog(CONTROLS.DIALOG_PAGE_LINK)},"Insert Visualization Link":function(){a.dialog(CONTROLS.DIALOG_VISUALIZATION_LINK)}});var f=$("<div><a id='embed-galaxy-object' class='action-button popup' href='#'>Embed Galaxy Object</a></div>").addClass("galaxy-page-editor-button");$(".wym_area_top").append(f),make_popupmenu(f,{"Embed History":function(){a.dialog(CONTROLS.DIALOG_EMBED_HISTORY)},"Embed Dataset":function(){a.dialog(CONTROLS.DIALOG_EMBED_DATASET)},"Embed Workflow":function(){a.dialog(CONTROLS.DIALOG_EMBED_WORKFLOW)},"Embed Visualization":function(){a.dialog(CONTROLS.DIALOG_EMBED_VISUALIZATION)}})});
//# sourceMappingURL=../maps/galaxy.pages.js.map