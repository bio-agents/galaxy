<%inherit file="/base.mako"/>
<%namespace file="/message.mako" import="render_msg" />

%if message:
    ${render_msg( message, status )}
%endif

<div class="agentForm">
    <div class="agentFormTitle">Change category name and description</div>
    <div class="agentFormBody">
        <form name="edit_category" action="${h.url_for( controller='admin', action='edit_category' )}" method="post" >
            <div class="form-row">
                <label>Name:</label>
                <div style="float: left; width: 250px; margin-right: 10px;">
                    <input type="text" name="name" value="${category.name | h}" size="40"/>
                </div>
                <div style="clear: both"></div>
            </div>
            <div class="form-row">
                <label>Description:</label>
                <div style="float: left; width: 250px; margin-right: 10px;">
                    <input  name="description" type="textfield" value="${category.description | h}" size=40"/>
                </div>
                <div style="clear: both"></div>
            </div>
            <div class="form-row">
                <div style="float: left; width: 250px; margin-right: 10px;">
                    <input type="hidden" name="rename" value="submitted"/>
                </div>
                <div style="clear: both"></div>
            </div>
            <div class="form-row">
                <div style="float: left; width: 250px; margin-right: 10px;">
                    <input type="hidden" name="id" value="${trans.security.encode_id( category.id )}"/>
                </div>
                <div style="clear: both"></div>
            </div>
            <div class="form-row">
                <input type="submit" name="edit_category_button" value="Save"/>
            </div>
        </form>
    </div>
</div>
