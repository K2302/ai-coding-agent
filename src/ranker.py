
def rank(semantic,bm25,git_score,dependency_score):
    return (
        semantic*0.4 +
        bm25*0.3 +
        git_score*0.15 +
        dependency_score*0.15
    )
