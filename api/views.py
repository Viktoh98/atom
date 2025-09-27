from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from .services import search_comapny, fetch_reviews
from .storage import load_json, save_json, logger



class CompanySearchView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        query = request.GET.get("query")
        if not query:
            return Response({"error": "query param required!"}, status=400)
        return Response(search_comapny(query))
    
    
class TrackCompanyListView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        tracked = load_json("tracked.json")
        return Response({"tracked": tracked})
    

class TrackCompanyCreateView(APIView):
    permission_classes = [IsAuthenticated]

    
    def post(self, request):
        domain = request.data.get("domain")
        if not domain:
            return Response({"error": "query param required!"}, status=400)
        tracked = load_json("tracked.json")
        if domain not in tracked:
            tracked.append(domain)
            save_json("tracked.json", tracked)
            logger(f"Added {domain} to tracking list")
            return Response({"message": f"Company {domain} added to tracking"}, status=201)
        else:
            return Response({"message": f"Company {domain} is already being tracked"}, status=200)
        
class TrackCompanyDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, domain=None):
        if not domain:
            return Response({"error": "domain param required!"}, status=400)

        tracked = load_json("tracked.json")
        if domain in tracked:
            tracked.remove(domain)
            save_json("tracked.json", tracked)
            logger(f"Removed {domain} from tracking list")
            return Response({"message": f"Company {domain} removed from tracking"}, status=200)

        return Response({"message": f"Company {domain} is not being tracked"}, status=404)
    
    
    
class ReviewView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, domain=None):
        if not domain:
            return Response({"error": "domain param required!"}, status=400)
        return Response(fetch_reviews(domain))
        
    