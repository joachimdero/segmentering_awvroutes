import arcpy

from functies import selecteer_netwerksegmenten, verrijk_segmenten_segmentering_vc, \
    maak_genummerde_routes, selecteer_segmenten_intersect_netwerk, attgenumweg, maak_split_points, \
    add_knooptype, verrijk_segmenten, segmenteer_netwerk, netwerk_gesegmenteerd_to_segmenten, \
    dissolve_kruispunten_rotondes,dprint





def maak_segmenten(segmenten, segmentering_vc, knopen, rijstroken):
    dprint()
    # voorbereiding
    # haal wegnummers op
    attgenumweg_table, attgenumweg_geom_dict, ws_oidn_ident2 = attgenumweg(cookie, segmenten)
    # verrijk segmenten met ident2
    segmenten_verrijkt = verrijk_segmenten(segmenten, ws_oidn_ident2)
    # verrijk knopen met knooptype, segmenten beschikken best over attr. wegnr,...
    add_knooptype(knopen, segmenten)
    # segmenten die deel gaan uitmaken van netwerk (enkel genummerde wegen,...)
    netwerksegmenten_selectie = selecteer_netwerksegmenten(segmenten_verrijkt, attgenumweg_geom_dict)
    #attgenumweg_fc, attgenumweg_dissolve
    netwerksegmenten_segmenten, netwerk_niet_gesegmenteerd = maak_genummerde_routes(netwerksegmenten_selectie, attgenumweg_table,
                                                        attgenumweg_geom_dict, rijstroken)
    # segmenten die geen deel uitmaken van netwerk maar het kruisen
    segmenten_intersect_netwerksegmenten = selecteer_segmenten_intersect_netwerk(segmenten_verrijkt,
                                                                                 netwerksegmenten_segmenten,
                                                                                 wbn)
    # selecteer knopen die gebruikt zullen worden om het netwerk te splitten in segmenten
    knopen_netwerksegmenten_split = maak_split_points(knopen, segmenten_verrijkt, netwerksegmenten_selectie,
                                                      segmenten_intersect_netwerksegmenten, wbn)
    # split netwerk
    netwerk_gesegmenteerd_tmp = segmenteer_netwerk(netwerk_niet_gesegmenteerd, knopen_netwerksegmenten_split)

    # voeg segmenten van rotondes en kruispunten toe samen als één netwerksegment
    netwerk_gesegmenteerd = dissolve_kruispunten_rotondes(
        netwerk_gesegmenteerd_tmp,
        segmenten,
        wbn,
        knopen_netwerksegmenten_split)


    # netwerk_id toevoegen aan segmenten
    netwerk_gesegmenteerd_to_segmenten(netwerk_gesegmenteerd, netwerksegmenten_segmenten)

    segmenten = verrijk_segmenten_segmentering_vc(segmenten_verrijkt, segmentering_vc)



# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    arcpy.env.workspace = r"C:\Users\derojp\Vlaamse overheid - Office 365\TeamAIM-BIM - Team_AssetBeheer_projecten\AddHoc\Segmentering\Segmentering20260602.gdb"
    arcpy.env.overwriteOutput = True
    segmenten = "WegsegmentVLA"
    knopen = "WegknoopVLA"
    rijstroken = "AttRijstrokenVLA"
    segmentering_vc = None
    cookie = "97e52d3501d04ab9860a57482f743e5b"
    wbn = r"C:\Users\derojp\Vlaamse overheid - Office 365\TeamAIM-BIM - Team_AssetBeheer_GisCommons\GISdata\grb.gdb\Wbn"

    maak_segmenten(segmenten, segmentering_vc, knopen, rijstroken)

