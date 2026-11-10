EDITABLE = ("name", "email")


def update_profile(user, form):
    """Apply the edit-profile form (name and email fields) to the user record."""
    for key in EDITABLE:
        if key in form:
            user[key] = form[key]
    return user
