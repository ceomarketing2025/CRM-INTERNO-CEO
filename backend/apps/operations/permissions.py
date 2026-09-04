def can_manage_operations(user): return bool(user.is_authenticated and (user.is_manager or user.role == "administration"))
