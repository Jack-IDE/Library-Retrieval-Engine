def run_controller(query, guidance, retrieve, rerank, compress):
    # pass 1
    candidates = retrieve(query, top_k=20, guidance=guidance)
    ranked = rerank(query, candidates, guidance=guidance)
    evidence = compress(ranked[:5], query)
    # pass 2
    expanded_query = query + " " + evidence
    candidates_2 = retrieve(expanded_query, top_k=20, guidance=guidance)
    ranked_2 = rerank(expanded_query, candidates_2, guidance=guidance)
    return ranked_2[:5], evidence
