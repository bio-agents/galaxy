<%def name="get_sort_url( sort_id, order, test_id, *args, **kwargs )">
    <%
        if sort_id == test_id:
            if order == "asc":
                agent_order = "desc"
            elif order == "desc":
                agent_order = "asc"
            else:
                agent_order = "default"
        else:
            agent_order = "default"
    %>
        
    %if len(kwargs.keys()) > 0:
        <a href="${h.url_for( controller=args[0], action=args[1], sort_id=test_id, order=agent_order, **kwargs )}">${" ".join(args[2:])}</a>
    %else:
        <a href="${h.url_for( controller=args[0], action=args[1], sort_id=test_id, order=agent_order )}">${" ".join(args[2:])}</a>
    %endif
</%def>

<%def name="get_css()">
    <style>
    .${sort_id} {
        visibility: visible
    }
    </style>
</%def>
