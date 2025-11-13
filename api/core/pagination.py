from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

DEFAULT_PAGE = 1


class CustomPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "perPage"

    def get_paginated_response(self, data, json=False):
        custom_paginator = {
            "data": data,
            "pagination": {
                "count": self.page.paginator.count,
                "total": self.page.paginator.num_pages,
                "perPage": int(self.request.GET.get("perPage", self.page_size)),
                "currentPage": int(self.request.GET.get("page", DEFAULT_PAGE)),
                "links": {"next": self.get_next_link(), "previous": self.get_previous_link()},
            },
        }
        if json is False:
            return Response(custom_paginator)
        else:
            return custom_paginator
