import importlib
import os
import re
import sys
import arcpy

try:
    from ....AwvFuncties import AuthenticatieProxyAcmAwv as Auth
    from ....AwvFuncties import Locatieservices2 as Ls2
    from ....AwvFuncties import WegenregisterAnalyse
    from ....AwvFuncties import AwvFuncties

    # importlib.reload(AwvFuncties.AuthenticatieProxyAcmAwv)
    # importlib.reload(AwvFuncties.Locatieservices2)
    importlib.reload(AwvFuncties.WegenregisterAnalyse)
    # importlib.reload(AwvFuncties)
except (ModuleNotFoundError, ImportError):
    basemap = "GIStools"
    basispath = os.path.realpath(__file__).split(basemap)[0]
    print("basispath = %s" % basispath)
    path2 = os.path.join(basispath, basemap, "AwvFuncties")
    sys.path.append(path2)
    import AuthenticatieProxyAcmAwv as Auth
    import Locatieservices2 as Ls2
    import WegenregisterAnalyse
    import AwvFuncties

    importlib.reload(Auth)
    importlib.reload(Ls2)
    importlib.reload(WegenregisterAnalyse)
    importlib.reload(AwvFuncties)


def selectie_knopen_netwerk_to_fc(segmenten, knopen):
    knopen_netwerk = "knopenSplit_tmp2eersteSelectieKnopen"
    if arcpy.Exists(knopen_netwerk):
        print(f"{knopen_netwerk} bestaat al")
        return knopen_netwerk
    print(f"selectie knopen van netwerksegmenten in {segmenten}")
    # selecteer knopen van netwerksegmenten
    wk_oidn_netwerksegmenten = tuple(set(
        val
        for row in arcpy.da.SearchCursor(segmenten, ["B_WK_OIDN", "E_WK_OIDN"])
        for val in row
    ))

    arcpy.CreateFeatureclass_management(
        out_path=arcpy.env.workspace,
        out_name=knopen_netwerk,
        geometry_type="POINT",
        template=knopen,
        spatial_reference=31370
    )

    with arcpy.da.SearchCursor(knopen, ["WK_OIDN", "*"]) as sc:
        with arcpy.da.InsertCursor(knopen_netwerk, ["WK_OIDN", "*"]) as ic:
            for row in sc:
                if row[0] in wk_oidn_netwerksegmenten:
                    ic.insertRow(row)
    print(f"{arcpy.GetCount_management(knopen_netwerk)[0]} knopen in {knopen_netwerk} na selectie 1")
    return knopen_netwerk


def selectie_knooptype_kruispunt(knopen_netwerk, segmenten):
    knopen_knooptype_kruispunt = "knopenSplit_tmp3tweedeSelectieKruispuntknopen"
    print(f"berekening knooptype op selectie van knopen in {knopen_netwerk} en {segmenten}")
    if arcpy.Exists(knopen_knooptype_kruispunt):
        print(f"{knopen_knooptype_kruispunt} bestaat al")
        return knopen_knooptype_kruispunt
    # berekenening knooptype met selectie van segmenten zodat er minder 'echte kruispunten' zijn
    f_knooptype = "knooptype_selectie"
    WegenregisterAnalyse.wegknooptype(knopen_netwerk, segmenten, f_knooptype="knooptype_selectie",
                                      spjoin="knopenSplit_tmp4spatialjoin")
    arcpy.ExportFeatures_conversion(
        in_features=knopen_netwerk,
        out_features=knopen_knooptype_kruispunt,
        where_clause=f"{f_knooptype} = 'knopen_overig'"

    )
    arcpy.AddMessage(
        f"{arcpy.GetCount_management(knopen_knooptype_kruispunt)[0]} knopen in {knopen_knooptype_kruispunt} na selectie 2")

    return knopen_knooptype_kruispunt


def selecteer_bijkomende_kruispuntknopen(knopen_knooptype_kruispunt, knopen_netwerk, wbn, segmenten):
    """
    Wanneer er een kruispuntknoop geselecteerd is van een T-kruispunt op een weg met gescheiden rijbanen,
    dan wordt de knoop op de andere rijbaan niet mee geselecteerd indien de 'doorsteek' een lage of geen wegcategorie heeft
    Deze functie selecteert bijkomende knopen op de andere rijbaan van het T-kruispunt.
    :param knopen_knooptype_kruispunt:
    :param knopen_netwerk:
    :param wbn:
    :param segmenten:
    :return:
    """
    bijkomende_kruispuntknopen = "knopenSplit_tmp5bijkomendeKruispuntknopen"
    if arcpy.Exists(bijkomende_kruispuntknopen):
        print(f"{bijkomende_kruispuntknopen} bestaat al")
        return bijkomende_kruispuntknopen
    kruispuntzone_lr = 'kruispuntzone_lr'
    # maak selectie kruispuntzones
    arcpy.MakeFeatureLayer_management(
        in_features=wbn,
        out_layer=kruispuntzone_lr,
        where_clause="LBLTYPE = 'kruispuntzone'"
    )
    arcpy.SelectLayerByLocation_management(
        in_layer=kruispuntzone_lr,
        overlap_type="INTERSECT",
        select_features=knopen_knooptype_kruispunt
    )
    # bereken knopen op aangepaste selectie segmenten
    segmenten_lr = "segmenten_selectie_morf"
    arcpy.MakeFeatureLayer_management(
        in_features=segmenten,
        out_layer=segmenten_lr,
        where_clause="LBLMORF IN ('weg bestaande uit één rijbaan','weg met gescheiden rijbanen die geen autosnelweg is')"
    )
    f_knooptype = "knooptype_selectie2"
    WegenregisterAnalyse.wegknooptype(knopen_netwerk, segmenten_lr, f_knooptype=f_knooptype,
                                      spjoin="wegknopen_spjoin2")
    # maak selectie knopen
    knopen_netwerk_lr = "knopen_netwerk_lr"
    arcpy.MakeFeatureLayer_management(
        in_features=knopen_netwerk,
        out_layer=knopen_netwerk_lr,
        where_clause=f"{f_knooptype} = 'knopen_overig'"
    )
    arcpy.SelectLayerByLocation_management(
        in_layer=knopen_netwerk_lr,
        overlap_type="INTERSECT",
        select_features=kruispuntzone_lr,
        selection_type="NEW_SELECTION"
    )
    arcpy.SelectLayerByLocation_management(
        in_layer=knopen_netwerk_lr,
        overlap_type="INTERSECT",
        select_features=knopen_knooptype_kruispunt,
        selection_type="REMOVE_FROM_SELECTION"
    )
    arcpy.SelectLayerByLocation_management(
        in_layer=knopen_netwerk_lr,
        overlap_type="WITHIN_A_DISTANCE",
        search_distance="20 Meters",
        select_features=knopen_knooptype_kruispunt,
        selection_type="SUBSET_SELECTION"
    )
    # Selecteer enkel knopen van gescheiden rijbanen
    gescheiden_rijbanen_lr = "netwerksegmenten_segmenten_lr"
    knopen_netwerk_lr = "knopen_netwerk_lr"
    arcpy.MakeFeatureLayer_management(
        in_features=netwerksegmenten_segmenten,
        out_layer=gescheiden_rijbanen_lr,
        where_clause="LBLMORF = 'weg met gescheiden rijbanen die geen autosnelweg is'"
    )
    arcpy.SelectLayerByLocation_management(
        in_layer=knopen_netwerk_lr,
        overlap_type="INTERSECT",
        select_features=gescheiden_rijbanen_lr,
        selection_type="SUBSET_SELECTION"
    )
    # TOEVOEGEN,INTERSECT MORFOLOGIE GESCHEIDEN RIJBAAN
    bijkomende_kruispuntknopen = "knopenSplit_tmp5bijkomendeKruispuntknopen"
    arcpy.ExportFeatures_conversion(
        in_features=knopen_netwerk_lr,
        out_features=bijkomende_kruispuntknopen
    )
    return bijkomende_kruispuntknopen


def selecteer_bijkomende_kruispuntknopen2(knopen_knooptype_kruispunt, knopen_netwerk, wbn, segmenten,
                                          netwerksegmenten_segmenten):
    """
    Wanneer er een kruispuntknoop geselecteerd is van een T-kruispunt op een weg met gescheiden rijbanen,
    dan wordt de knoop op de andere rijbaan niet mee geselecteerd indien de 'doorsteek' een lage of geen wegcategorie heeft
    Deze functie selecteert bijkomende knopen op de andere rijbaan van het T-kruispunt.
    :param knopen_knooptype_kruispunt:
    :param knopen_netwerk:
    :param wbn:
    :param segmenten:
    :return:
    """
    arcpy.AddMessage(f"selecteer_bijkomende_kruispuntknopen2".upper())
    arcpy.AddMessage(f"knopen_knooptype_kruispunt: {knopen_knooptype_kruispunt}")
    arcpy.AddMessage(f"knopen_netwerk: {knopen_netwerk}")
    arcpy.AddMessage(f"segmenten: {segmenten}")

    bijkomende_kruispuntknopen = "knopenSplit_tmp5bijkomendeKruispuntknopen"
    if arcpy.Exists(bijkomende_kruispuntknopen):
        print(f"{bijkomende_kruispuntknopen} bestaat al")
        return bijkomende_kruispuntknopen
    # er moeten enkel bijkomende knopen geselecteerd worden voor kruispunten op wegen met gescheiden rijbanen.
    # deze moeten in de buurt liggen van een reeds geselecteerde kruispuntknoop
    # → selecteer de netwerksegmenten_segmenten met morfologie 'weg met gescheiden rijbanen die geen autosnelweg is'
    netwerksegmenten_gescheiden_rijbanen_lyr = "netwerksegmenten_gescheiden_rijbanen_lyr"
    arcpy.MakeFeatureLayer_management(
        in_features=netwerksegmenten_segmenten,
        out_layer=netwerksegmenten_gescheiden_rijbanen_lyr,
        where_clause="LBLMORF = 'weg met gescheiden rijbanen die geen autosnelweg is'"
    )
    arcpy.SaveToLayerFile_management(
        in_layer=netwerksegmenten_gescheiden_rijbanen_lyr,
        out_layer=str(netwerksegmenten_gescheiden_rijbanen_lyr)
    )

    # → selecteer de knopen van type 'knopen_overig' die IN deze segmenten liggen.
    knopen_knooptype_kruispunt_lyr = "knopen_knooptype_kruispunt_intersect_gescheiden_rijbaan_lyr"
    arcpy.MakeFeatureLayer_management(
        in_features=knopen_knooptype_kruispunt,
        out_layer=knopen_knooptype_kruispunt_lyr,
        where_clause="knooptype_selectie = 'knopen_overig'"
    )
    arcpy.AddMessage(
        f"{arcpy.GetCount_management(knopen_knooptype_kruispunt_lyr)[0]} knopen in knopen_knooptype_kruispunt_lyr")
    arcpy.SelectLayerByLocation_management(
        in_layer=knopen_knooptype_kruispunt_lyr,
        overlap_type="INTERSECT",
        select_features=netwerksegmenten_gescheiden_rijbanen_lyr,
        selection_type="NEW_SELECTION"
    )
    arcpy.AddMessage(
        f"{arcpy.GetCount_management(knopen_knooptype_kruispunt_lyr)[0]} knopen in {knopen_knooptype_kruispunt_lyr} na selectie 'intersect gescheiden rijbaan'")

    knopen_kruispuntknoop_gescheidenrijbaan = "knopenSplit_tmp7knopenKruispuntIntersectGescheidenRijbaan"
    arcpy.ExportFeatures_conversion(
        in_features=knopen_knooptype_kruispunt_lyr,
        out_features=knopen_kruispuntknoop_gescheidenrijbaan
    )

    # Selecteer segmenten die dienen voor de knoopberekening
    # → maak een subselectie van segmenten met morfologie 'weg met gescheiden rijbanen die geen autosnelweg is'
    # of 'weg bestaande uit één rijbaan'
    segmenten_selectie1_morf_lyr = "segmenten_selectie1_morf"
    arcpy.MakeFeatureLayer_management(
        in_features=segmenten,  # alle wegsegmenten
        out_layer=segmenten_selectie1_morf_lyr,
        where_clause="LBLMORF IN ('weg bestaande uit één rijbaan','weg met gescheiden rijbanen die geen autosnelweg is') AND Shape_length < 20"
    )

    # → selecteer segmenten die de reeds geselecteerde kruispuntknopen raken + segmenten die deze segmenten raken,
    # deselecteer de segmenten die buiten de kruispuntzone liggen
    segmenten_selectie2_intersectkruispuntknopen_lyr = "segmenten_selectie2_intersectkruispuntknopen"
    arcpy.MakeFeatureLayer_management(
        in_features=segmenten_selectie1_morf_lyr,  # alle wegsegmenten
        out_layer=segmenten_selectie2_intersectkruispuntknopen_lyr,
    )
    arcpy.SelectLayerByLocation_management(
        in_layer=segmenten_selectie2_intersectkruispuntknopen_lyr,
        overlap_type="INTERSECT",
        select_features=knopen_kruispuntknoop_gescheidenrijbaan,
        selection_type="NEW_SELECTION"
    )
    arcpy.SelectLayerByLocation_management(
        in_layer=segmenten_selectie2_intersectkruispuntknopen_lyr,
        overlap_type="INTERSECT",
        select_features=segmenten_selectie2_intersectkruispuntknopen_lyr,
        selection_type="ADD_TO_SELECTION"
    )
    segmenten_selectie2_intersectkruispuntknopen = "knopensplit_tmp6segmentenSelectie2_intersectKruispuntknopen"
    arcpy.ExportFeatures_conversion(
        in_features=segmenten_selectie2_intersectkruispuntknopen_lyr,
        out_features=segmenten_selectie2_intersectkruispuntknopen
    )
    kruispuntzone_lr = 'kruispuntzone_lr'
    # maak selectie kruispuntzones
    arcpy.MakeFeatureLayer_management(
        in_features=wbn,
        out_layer=kruispuntzone_lr,
        where_clause="LBLTYPE = 'kruispuntzone'"
    )
    arcpy.SelectLayerByLocation_management(
        in_layer=segmenten_selectie2_intersectkruispuntknopen_lyr,
        overlap_type="COMPLETELY_WITHIN",
        select_features=kruispuntzone_lr,
        selection_type="SUBSET_SELECTION"
    )
    segmenten_selectie4_within_kruispuntzone="knopensplit_tmp7segmentenBinnenKruispuntzone"
    arcpy.ExportFeatures_conversion(
        in_features=segmenten_selectie2_intersectkruispuntknopen_lyr,
        out_features=segmenten_selectie4_within_kruispuntzone
    )
    arcpy.AddMessage(
        f"{arcpy.GetCount_management(segmenten_selectie4_within_kruispuntzone)[0]} segmenten in selectie2")


    # → selecteer de segmenten die nodig zijn om de knoopberekening te doen
    # (netwerksegmenten + selectie korte segmenten binnen kruispuntzone)
    # Selectie netwerksegmenten in de buurt van potentiële kruispuntknopen
    netwerksegmenten_knoopberekening_lyr = "netwerksegmenten_knoopberekening"
    arcpy.MakeFeatureLayer_management(
        in_features=netwerksegmenten_segmenten,  # alle wegsegmenten
        out_layer=netwerksegmenten_knoopberekening_lyr,
    )
    arcpy.SelectLayerByLocation_management(
        in_layer=netwerksegmenten_knoopberekening_lyr,
        overlap_type="INTERSECT",
        select_features=segmenten_selectie4_within_kruispuntzone,
        selection_type="NEW_SELECTION"
    )
    arcpy.SelectLayerByLocation_management(
        in_layer=netwerksegmenten_knoopberekening_lyr,
        overlap_type="ARE_IDENTICAL_TO",
        select_features=segmenten_selectie4_within_kruispuntzone,
        selection_type="REMOVE_FROM_SELECTION"
    )
    segmenten_knoopberekening = "knopensplit_tmp8segmentenKnoopberekening"

    arcpy.Merge_management(
        inputs=[netwerksegmenten_knoopberekening_lyr, segmenten_selectie4_within_kruispuntzone],
        output=segmenten_knoopberekening
    )


    # bereken knooptype op deze selectie van segmenten
    f_knooptype = "knooptype_selectie2"
    WegenregisterAnalyse.wegknooptype(knopen_netwerk, segmenten_knoopberekening, f_knooptype=f_knooptype,
                                      spjoin="wegknopen_spjoin2")
    # deselecteer reeds geselecteerde kruispuntknopen
    # maak selectie knopen
    print(f"{arcpy.GetCount_management(knopen_knooptype_kruispunt)[0]} knopen in {knopen_knooptype_kruispunt}")
    knopen_netwerk_lr = "knopen_netwerk_lr"
    print(f"path knopen_netwerk: {arcpy.Describe(knopen_netwerk).catalogPath}")
    print(f"path knopen_netwerk: {arcpy.Describe(knopen_knooptype_kruispunt).catalogPath}")
    arcpy.MakeFeatureLayer_management(
        in_features=knopen_netwerk,
        out_layer=knopen_netwerk_lr,
        where_clause=f"{f_knooptype} = 'knopen_overig'"
    )
    print(f"{arcpy.GetCount_management(knopen_netwerk_lr)[0]} knopen in {arcpy.Describe(knopen_netwerk_lr).catalogPath}")
    arcpy.MakeFeatureLayer_management(
        in_features=knopen_knooptype_kruispunt,
        out_layer="knopen_knooptype_kruispunt_lyr2"
    )
    print(f"{arcpy.GetCount_management('knopen_knooptype_kruispunt_lyr2')[0]} knopen in {'knopen_knooptype_kruispunt_lyr2'}")
    arcpy.SelectLayerByLocation_management(
        in_layer=knopen_netwerk_lr,
        overlap_type="INTERSECT",
        select_features="knopen_knooptype_kruispunt_lyr2",
        search_distance = "1 Meters",
        selection_type="NEW_SELECTION",
        invert_spatial_relationship="INVERT"
    )
    print(f"{arcpy.GetCount_management(knopen_netwerk_lr)[0]} knopen in {knopen_netwerk_lr}")
    arcpy.SelectLayerByLocation_management(
        in_layer=knopen_netwerk_lr,
        overlap_type="INTERSECT",
        select_features=netwerksegmenten_gescheiden_rijbanen_lyr,
        search_distance = "0.1 Meters",
        selection_type="SUBSET_SELECTION"
    )
    print(f"{arcpy.GetCount_management(knopen_netwerk_lr)[0]} knopen in {knopen_netwerk_lr}")

    # TOEVOEGEN,INTERSECT MORFOLOGIE GESCHEIDEN RIJBAAN
    bijkomende_kruispuntknopen = "knopenSplit_tmp5bijkomendeKruispuntknopen"
    arcpy.ExportFeatures_conversion(
        in_features=knopen_netwerk_lr,
        out_features=bijkomende_kruispuntknopen
    )
    return bijkomende_kruispuntknopen
