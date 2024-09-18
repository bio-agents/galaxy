define(["utils/utils"],function(a){return{grid:function(a){var b="";return b=a.embedded?this.grid_header(a)+this.grid_table(a):'<div class="loading-elt-overlay"></div><table><tr><td width="75%">'+this.grid_header(a)+'</td><td></td><td></td></tr><tr><td width="100%" id="grid-message" valign="top"></td><td></td><td></td></tr></table>'+this.grid_table(a),a.info_text&&(b+='<br><div class="agentParamHelp" style="clear: both;">'+a.info_text+"</div>"),b},grid_table:function(){return'<form method="post" onsubmit="return false;"><table id="grid-table" class="grid"><thead id="grid-table-header"></thead><tbody id="grid-table-body"></tbody><tfoot id="grid-table-footer"></tfoot></table></form>'},grid_header:function(a){var b='<div class="grid-header">';if(a.embedded||(b+="<h2>"+a.title+"</h2>"),a.global_actions){b+='<ul class="manage-table-actions">';var c=a.global_actions.length>=3;c&&(b+='<li><a class="action-button" id="popup-global-actions" class="menubutton">Actions</a></li><div popupmenu="popup-global-actions">');for(i in a.global_actions){var d=a.global_actions[i],e="";e=d.inbound?"use-inbound":"use-outbound",b+='<li><a class="action-button '+e+'" href="'+d.url_args+'" onclick="return false;">'+d.label+"</a></li>"}c&&(b+="</div>"),b+="</ul>"}return a.insert&&(b+=a.insert),b+=this.grid_filters(a),b+="</div>"},header:function(a){var b="<tr>";a.show_item_checkboxes&&(b+="<th>",a.items.length>0&&(b+='<input type="checkbox" id="check_all" name=select_all_checkbox value="true"><input type="hidden" name=select_all_checkbox value="true">'),b+="</th>");for(var c in a.columns){var d=a.columns[c];d.visible&&(b+='<th id="'+d.key+'-header">',b+=d.href?'<a href="'+d.href+'" class="sort-link" sort_key="'+d.key+'">'+d.label+"</a>":d.label,b+='<span class="sort-arrow">'+d.extra+"</span></th>")}return b+="</tr>"},body:function(a){var b="",c=0,d=a.items.length;0==d&&(b+='<tr><td colspan="100"><em>No Items</em></td></tr>',c=1);for(var e in a.items){var f=a.items[e],g=f.encode_id;b+="<tr ",a.current_item_id==f.id&&(b+='class="current"'),b+=">",a.show_item_checkboxes&&(b+='<td style="width: 1.5em;"><input type="checkbox" name="id" value="'+g+'" id="'+g+'" class="grid-row-select-checkbox" /></td>');for(j in a.columns){var h=a.columns[j];if(h.visible){var i="";h.nowrap&&(i='style="white-space:nowrap;"');var k=f.column_config[h.label],l=k.link,m=k.value,n=k.inbound;"string"===jQuery.type(m)&&(m=m.replace(/\/\//g,"/"));var o="",p="";if(h.attach_popup&&(o="grid-"+e+"-popup",p="menubutton",""!=l&&(p+=" split"),p+=" popup"),b+="<td "+i+">",l){0!=a.operations.length&&(b+='<div id="'+o+'" class="'+p+'" style="float: left;">');var q="";q=n?"use-inbound":"use-outbound",b+='<a class="menubutton-label '+q+'" href="'+l+'" onclick="return false;">'+m+"</a>",0!=a.operations.length&&(b+="</div>")}else b+='<div id="'+o+'" class="'+p+'"><label id="'+h.label_id_prefix+g+'" for="'+g+'">'+(m||"")+"</label></div>";b+="</td>"}}b+="</tr>",c++}return b},footer:function(a){var b="";if(a.use_paging&&a.num_pages>1){var c=a.num_page_links,d=a.cur_page_num,e=a.num_pages,f=c/2,g=d-f,h=0;0>=g&&(g=1,h=f-(d-g));var j=f+h,k=d+j;e>=k?max_offset=0:(k=e,max_offset=j-(k+1-d)),0!=max_offset&&(g-=max_offset,1>g&&(g=1)),b+='<tr id="page-links-row">',a.show_item_checkboxes&&(b+="<td></td>"),b+='<td colspan="100"><span id="page-link-container">Page:',g>1&&(b+='<span class="page-link" id="page-link-1"><a href="javascript:void(0);" page_num="1" onclick="return false;">1</a></span> ...');for(var l=g;k+1>l;l++)b+=l==a.cur_page_num?'<span class="page-link inactive-link" id="page-link-'+l+'">'+l+"</span>":'<span class="page-link" id="page-link-'+l+'"><a href="javascript:void(0);" onclick="return false;" page_num="'+l+'">'+l+"</a></span>";e>k&&(b+='...<span class="page-link" id="page-link-'+e+'"><a href="javascript:void(0);" onclick="return false;" page_num="'+e+'">'+e+"</a></span>"),b+="</span>",b+='<span class="page-link" id="show-all-link-span"> | <a href="javascript:void(0);" onclick="return false;" page_num="all">Show All</a></span></td></tr>'}if(a.show_item_checkboxes){b+='<tr><input type="hidden" id="operation" name="operation" value=""><td></td><td colspan="100">For <span class="grid-selected-count"></span> selected '+a.get_class_plural+": ";for(i in a.operations){var m=a.operations[i];m.allow_multiple&&(b+='<input type="button" value="'+m.label+'" class="operation-button action-button">&nbsp;')}b+="</td></tr>"}var n=!1;for(i in a.operations)if(a.operations[i].global_operation){n=!0;break}if(n){b+='<tr><td colspan="100">';for(i in a.operations){var m=a.operations[i];m.global_operation&&(b+='<a class="action-button" href="'+m.global_operation+'">'+m.label+"</a>")}b+="</td></tr>"}return a.legend&&(b+='<tr><td colspan="100">'+a.legend+"</td></tr>"),b},message:function(a){return'<p><div class="'+a.status+'message transient-message">'+a.message+'</div><div style="clear: both"></div></p>'},grid_filters:function(a){var b=a.default_filter_dict,c=a.filters,d="none";a.advanced_search&&(d="block");var e=!1;for(var f in a.columns){var g=a.columns[f];if("advanced"==g.filterable){var h=g.key,i=c[h],j=b[h];i&&j&&i!=j&&(d="block"),e=!0}}var k="block";"block"==d&&(k="none");var l='<div id="standard-search" style="display: '+k+';"><table><tr><td style="padding: 0;"><table>';for(var f in a.columns){var g=a.columns[f];"standard"==g.filterable&&(l+=this.grid_column_filter(a,g))}l+="</table></td></tr><tr><td>",e&&(l+='<a href="" class="advanced-search-toggle">Advanced Search</a>'),l+="</td></tr></table></div>",l+='<div id="advanced-search" style="display: '+d+'; margin-top: 5px; border: 1px solid #ccc;"><table><tr><td style="text-align: left" colspan="100"><a href="" class="advanced-search-toggle">Close Advanced Search</a></td></tr>';for(var f in a.columns){var g=a.columns[f];"advanced"==g.filterable&&(l+=this.grid_column_filter(a,g))}return l+="</table></div>"},grid_column_filter:function(a,b){var c=(a.default_filter_dict,a.filters),d=b.label,e=b.key;"advanced"==b.filterable&&(d=d.toLowerCase());var f="<tr>";if("advanced"==b.filterable&&(f+='<td align="left" style="padding-left: 10px">'+d+":</td>"),f+='<td style="padding-bottom: 1px;">',b.is_text){f+='<form class="text-filter-form" column_key="'+e+'" action="'+a.url+'" method="get" >';for(k in a.columns){var g=a.columns[k],h=c[g.key];h&&"All"!=h&&(g.is_text&&(h=JSON.stringify(h)),f+='<input type="hidden" id="'+g.key+'" name="f-'+g.key+'" value="'+h+'"/>')}f+='<span id="'+e+'-filtering-criteria">';var i=c[e];if(i){var j=jQuery.type(i);if("string"==j&&"All"!=i&&(f+=this.filter_element(e,i)),"array"==j)for(var k in i){var l=i[k],m=i;m=m.slice(k),f+=this.filter_element(e,l)}}f+="</span>";var n="";if("standard"==b.filterable){n=b.label.toLowerCase();var o=n.length;20>o&&(o=20),o+=4}f+='<span class="search-box"><input class="search-box-input" id="input-'+e+'-filter" name="f-'+e+'" type="text" placeholder="'+n+'" size="'+o+'"/><button type="submit" style="background: transparent; border: none; padding: 4px; margin: 0px;"><i class="fa fa-search"></i></button></span></form>'}else{f+='<span id="'+e+'-filtering-criteria">';var p=!1;for(cf_label in a.categorical_filters[e]){var q=a.categorical_filters[e][cf_label],r="",s="";for(key in q)r=key,s=q[key];p&&(f+=" | "),p=!0;var l=c[e];f+=l&&q[e]&&l==s?'<span class="categorical-filter '+e+'-filter current-filter">'+cf_label+"</span>":'<span class="categorical-filter '+e+'-filter"><a href="javascript:void(0);" filter_key="'+r+'" filter_val="'+s+'">'+cf_label+"</a></span>"}f+="</span>"}return f+="</td></tr>"},filter_element:function(b,c){return c=a.sanitize(c),'<span class="text-filter-val">'+c+'<a href="javascript:void(0);" filter_key="'+b+'" filter_val="'+c+'"><i class="fa fa-times" style="padding-left: 5px; padding-bottom: 6px;"/></a></span>'}}});
//# sourceMappingURL=../../../maps/mvc/grid/grid-template.js.map