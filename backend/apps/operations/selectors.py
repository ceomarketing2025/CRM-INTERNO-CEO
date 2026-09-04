from .models import GeneralManagementRecord, ProductionRecord

def recent_general_records(limit=20): return GeneralManagementRecord.objects.select_related("client").all()[:limit]
def recent_production(limit=20): return ProductionRecord.objects.select_related("client", "collaborator").all()[:limit]
