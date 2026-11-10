def update_profile(user, form):
    """Apply the edit-profile form (name and email fields) to the user record."""
    user.update(form)
    return user
