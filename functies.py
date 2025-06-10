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


def selectie_wegnummer(wegnummer):
    # Type 1: ident8 (bijv. N2820001)
    if re.fullmatch(r"[A-Z]\d{7}", wegnummer):
        if wegnummer[4] != "7" and int(wegnummer[4:7]) <= 926 and not (wegnummer[0] == 'N' and wegnummer[4] == "5"):
            return True

    # Type 2: baannummer (bijv. N1h1, N1ah1, A789h2) → eindigt op h1 of h2
    elif re.fullmatch(r"[A-Z][a-z]?\d{1,3}[a-z]\d{1,2}", wegnummer):
        if wegnummer.endswith("h1") or wegnummer.endswith("h2"):
            return True

    return False


def attgenumweg(cookie, segmenten):
    def maak_tabel_attgenumweg_(cookie):
        attgenumweg_table = "attgenumweg_tmp1TableFromLs2"
        if arcpy.Exists(attgenumweg_table):
            return attgenumweg_table
        else:
            session = Auth.prepareSession(cookie=cookie)
            session = Auth.proxieHandler(session)
            Ls2.attgenumweg(session, attgenumweg_table)

            return attgenumweg_table

    def attgenumweg_werkdata(attgenumweg_table):
        ws_oidn_ident2 = {}
        attgenumweg_wsoidns = set()

        with arcpy.da.SearchCursor(attgenumweg_table, ["ws_oidn", "wegnummer"]) as sc:
            for ws_oidn, wegnummer in sc:
                if selectie_wegnummer(wegnummer):  # onbelangrijke wegen op basis van wegnummer uitsluiten
                    attgenumweg_wsoidns.add(ws_oidn)
                    ident2 = AwvFuncties.ident8_to_ident2(wegnummer)
                    if ident2 != "":
                        ws_oidn_ident2[ws_oidn] = ident2
                    elif ws_oidn not in ws_oidn_ident2:
                        ws_oidn_ident2[ws_oidn] = None
        return attgenumweg_wsoidns, ws_oidn_ident2

    def maak_dict_geom(segmenten, attgenumweg_wsoidns):
        f_sc = ["SHAPE@", "ws_oidn"]
        geom_segmenten = {row[1]: row[0] for row in arcpy.da.SearchCursor(segmenten, f_sc) if
                          row[1] in attgenumweg_wsoidns}
        return geom_segmenten

    attgenumweg_table = maak_tabel_attgenumweg_(cookie)
    attgenumweg_wsoidns, ws_oidn_ident2 = attgenumweg_werkdata(attgenumweg_table)
    attgenumweg_geom_dict = maak_dict_geom(segmenten, attgenumweg_wsoidns)

    return attgenumweg_table, attgenumweg_geom_dict, ws_oidn_ident2


def verrijk_segmenten(segmenten, ws_oidn_ident2):
    def add_ident2(segmenten, ws_oidn_ident2):
        if "ident2" not in [f.name.lower() for f in arcpy.ListFields(segmenten)]:
            arcpy.AddField_management(segmenten, "ident2", "TEXT", field_length=6)
        with arcpy.da.UpdateCursor(segmenten, ["ws_oidn", "ident2"]) as uc:
            for row in uc:
                row[1] = ws_oidn_ident2.get(row[0], "")
                uc.updateRow(row)

    add_ident2(segmenten, ws_oidn_ident2)


def add_knooptype(knopen, segmenten):
    if "knooptype" in [f.name for f in arcpy.ListFields(knopen)]:
        arcpy.AddMessage("veld knooptype bestaat reeds en wordt niet herrekend")
    else:
        arcpy.AddMessage(f"veld knooptype wordt berekend voor {knopen}")
        segmenten_lr = "segmenten_selectie_morf"
        arcpy.MakeFeatureLayer_management(
            in_features=segmenten,
            out_layer=segmenten_lr,
            where_clause="LBLMORF NOT IN ('dienstweg','aardeweg','wandel- of fietsweg, niet toegankelijk voor andere voertuigen','tramweg, niet toegankelijk voor andere voertuigen')"
        )
        WegenregisterAnalyse.wegknooptype(knopen, segmenten, f_knooptype="knooptype")


def selecteer_netwerksegmenten(segmenten, attgenumweg_geom_dict):
    netwerksegmenten_segmenten = "netwerksegmenten_segmenten"
    arcpy.AddMessage(f"{'selecteer_netwerksegmenten'.upper()} => {netwerksegmenten_segmenten}")
    # maak een selectie van wegsegmenten
    # de selectie moet de segmenten bevatten die je wil groeperen in netwerksegmenten
    if arcpy.Exists(netwerksegmenten_segmenten):
        return netwerksegmenten_segmenten
    geom_segmenten_wsoidn = tuple(attgenumweg_geom_dict.keys())
    selectie_morf = (101, 102, 103, 105, 104, 106, 107, 109, 110)
    selectie_wegcategorie = ('EHW', 'H', 'IW', 'L1', 'OW', 'PI', 'PII', 'RW', 'S', 'S1', 'S2', 'S3', 'S4', 'VHW')
    where_clause = (
        # f"wegcat IN {selectie_wegcategorie} AND "
        f"lblbeheer LIKE '%District%' AND "
        f"(lblstatus = 'in gebruik') AND "
        f"(lbltgbep = 'openbare weg') AND "
        f"(ws_oidn IN {geom_segmenten_wsoidn}) AND "
        # f"(doorsteek IN ('0')) AND "
        f"(morf IN {selectie_morf})"
    )

    def fieldmapping(segmenten):
        field_mappings = arcpy.FieldMappings()
        field_map = arcpy.FieldMap()
        field_map.addInputField(segmenten, "ws_oidn")
        field_mappings.addFieldMap(field_map)
        field_map.addInputField(segmenten, "ident2")
        field_mappings.addFieldMap(field_map)

    arcpy.ExportFeatures_conversion(
        in_features=segmenten,
        out_features=netwerksegmenten_segmenten,
        where_clause=where_clause,
        field_mapping=fieldmapping(segmenten)
    )

    arcpy.AddMessage(f"{arcpy.GetCount_management(netwerksegmenten_segmenten)} netwerksegmenten_segmenten")
    return netwerksegmenten_segmenten


def selecteer_segmenten_intersect_netwerksegmenten(segmenten, netwerksegmenten_segmenten, wbn):
    arcpy.AddMessage(f"{'selecteer_segmenten_intersect_netwerksegmenten'.upper()}, bron:{segmenten}")
    # maak een selectie van wegsegmenten
    # de selectie moet de segmenten bevatten die je wil groeperen in netwerksegmenten en de segmenten waar je
    # de netwerksegmenten wil splitten
    segmenten_intersect_netwerksegmenten = "segmenten_intersect_netwerksegmenten"
    if arcpy.Exists(segmenten_intersect_netwerksegmenten):
        arcpy.AddMessage(f"{segmenten_intersect_netwerksegmenten} bestaat reeds")
        return segmenten_intersect_netwerksegmenten

    selectie_morf = (102, 103, 104, 105, 106, 109, 110)#107,
    selectie_wegcategorie = ('EHW', 'H', 'IW', 'L1', 'OW', 'PI', 'PII', 'RW', 'S', 'S1', 'S2', 'S3', 'S4', 'VHW')
    where_clause = (
        f"(wegcat IN {selectie_wegcategorie})AND "
        f"(lblstatus = 'in gebruik') AND "
        f"(lbltgbep = 'openbare weg') AND "
        # f"(doorsteek IN ('0')) AND "
        f"(morf IN {selectie_morf})"
    )

    # Stap 1: Maak een lijst met OBJECTID's van netwerksegmenten_segmenten
    netwerksegmenten_segmenten_wsoidns = set(
        row[0] for row in arcpy.da.SearchCursor(netwerksegmenten_segmenten, ["WS_OIDN"]))

    # Stap 2: Zoek begin- en eindpunten van fc2-netwerksegmenten_segmenten
    netwerksegmenten_segmenten_endpoints = set()
    with arcpy.da.SearchCursor(netwerksegmenten_segmenten, ["SHAPE@"]) as sc:
        for row in sc:
            geom = row[0]
            netwerksegmenten_segmenten_endpoints.add((round(geom.firstPoint.X, 3), round(geom.firstPoint.Y, 3)))
            netwerksegmenten_segmenten_endpoints.add((round(geom.lastPoint.X, 3), round(geom.lastPoint.Y, 3)))

    # Stap 3: Selecteer lijnen uit segmenten die niet in netwerksegmenten_segmenten zitten én waarvan het begin- of eindpunt in fc2_endpoints zit
    arcpy.CreateFeatureclass_management(
        out_path=arcpy.env.workspace,
        out_name=segmenten_intersect_netwerksegmenten,
        geometry_type="POLYLINE",
        spatial_reference=31370
    )

    fields_add = ["WS_OIDN", "LBLMORF", "B_WK_OIDN", "E_WK_OIDN", "LSTRNM", "RSTRNM", "LBLWEGCAT"]
    fields_add_desc = [f for f in arcpy.ListFields(segmenten) if
                       f.name in fields_add and f.type not in ("OID", "Geometry")]
    for f in fields_add_desc:
        arcpy.AddField_management(segmenten_intersect_netwerksegmenten, f.name, f.type, f.length)

    def selecteer_exporteer_intersect_segmenten(segmenten, where_clause, netwerksegmenten_segmenten_wsoidns):
        f_cursors = ["SHAPE@"] + fields_add
        with arcpy.da.SearchCursor(segmenten, f_cursors, where_clause) as sc, \
                arcpy.da.InsertCursor(segmenten_intersect_netwerksegmenten, f_cursors) as ic:
            for i, (geom, ws_oidn, lblmorf, b_wk_oidn, e_wk_oidn, lstrnm, rstrnm, lblwegcat) in enumerate(sc):
                if ws_oidn in netwerksegmenten_segmenten_wsoidns:
                    continue  # overslaan als hij ook in netwerksegmenten_segmenten_wsoidns zit

                start = (round(geom.firstPoint.X, 3), round(geom.firstPoint.Y, 3))
                end = (round(geom.lastPoint.X, 3), round(geom.lastPoint.Y, 3))

                if start in netwerksegmenten_segmenten_endpoints or end in netwerksegmenten_segmenten_endpoints:
                    ic.insertRow((geom, ws_oidn, lblmorf, b_wk_oidn, e_wk_oidn, lstrnm, rstrnm, lblwegcat))

    selecteer_exporteer_intersect_segmenten(segmenten, where_clause, netwerksegmenten_segmenten_wsoidns)
    # bijkomende_kruispuntsegmenten = selecteer_bijkomende_kruispuntsegmenten(segmenten_intersect_netwerksegmenten, wbn, segmenten)
    # selecteer_exporteer_intersect_segmenten(bijkomende_kruispuntsegmenten, where_clause, netwerksegmenten_segmenten_wsoidns)
    aantal_segmenten = arcpy.GetCount_management(segmenten_intersect_netwerksegmenten)[0]
    arcpy.AddMessage(
        f"{aantal_segmenten} segmenten in {segmenten_intersect_netwerksegmenten}")

    return segmenten_intersect_netwerksegmenten


def verrijk_segmenten_segmentering_vc(segmenten, segmentering_vc):
    # join
    # calculate ident2plus
    return segmenten


def maak_genummerde_routes(netwerksegmenten_segmenten, attgenumweg_table, geom_segmenten):
    attgenumweg_dissolve = "attgenumweg_tmp3Dissolve"
    if arcpy.Exists(attgenumweg_dissolve):
        arcpy.AddMessage(f"{attgenumweg_dissolve} bestaat reeds")
        return attgenumweg_dissolve


    def add_geometry_to_attgenumweg(geom_segmenten, attgenumweg_table):
        attgenumweg_fc = "attgenumweg_fc_tmp2AddGeometry"
        arcpy.AddMessage(f"add_geometry_to_attgenumweg => {attgenumweg_fc}")
        arcpy.CreateFeatureclass_management(
            out_path=arcpy.env.workspace,
            out_name=attgenumweg_fc,
            geometry_type="POLYLINE",
            template=attgenumweg_table,
            spatial_reference=31370
        )

        def reverse_polyline(polyline):
            """Keert de richting van een arcpy.Polyline om (geen multipart)."""
            part = polyline.getPart(0)  # Eerste (en enige) deel van de lijn
            reversed_array = arcpy.Array([pt for pt in reversed(part)])
            return arcpy.Polyline(reversed_array, polyline.spatialReference)

        netwerksegmenten_segmenten_ws_oidn = set(
            [row[0] for row in arcpy.da.SearchCursor(netwerksegmenten_segmenten, "ws_oidn")])
        f_sc = ["ws_oidn", "wegnummer", "richting"]
        f_ic = ["SHAPE@"] + f_sc
        ic = arcpy.da.InsertCursor(attgenumweg_fc, f_ic)
        with arcpy.da.SearchCursor(attgenumweg_table, f_sc) as sc:
            for ws_oidn, wegnummer, richting in sc:
                if ws_oidn in geom_segmenten and ws_oidn in netwerksegmenten_segmenten_ws_oidn:
                    geom = geom_segmenten[ws_oidn]
                    if richting == 2:
                        geom = reverse_polyline(geom)
                    row_new = [geom, ws_oidn, wegnummer, richting]
                    ic.insertRow(row_new)
        return attgenumweg_fc

    attgenumweg_fc = add_geometry_to_attgenumweg(geom_segmenten, attgenumweg_table)

    arcpy.Dissolve_management(
        in_features=attgenumweg_fc,
        out_feature_class=attgenumweg_dissolve,
        dissolve_field="wegnummer",
        multi_part="SINGLE_PART"
    )
    arcpy.AddMessage(f"{arcpy.GetCount_management(attgenumweg_dissolve)} netwerkroutes in {attgenumweg_dissolve}")

    return attgenumweg_dissolve


def maak_split_points(knopen, segmenten, netwerksegmenten_segmenten, segmenten_intersect_netwerksegmenten, wbn):
    # selecteer knopen op basis van netwerksegmenten_segmenten
    # selecteer kruispuntknopen op basis van netwerksegmenten_segmenten + segmenten_intersect_netwerksegmenten
    knopen_split = "knopenSplit"
    # voorbereiding segmenten
    netwerksegmenten_intersect_merge = "knopenSplit_tmp1selectiewegsegmenten"
    arcpy.AddMessage(f"maak_split_points".upper())
    arcpy.Merge_management([netwerksegmenten_segmenten, segmenten_intersect_netwerksegmenten], netwerksegmenten_intersect_merge)

    def selectie_knopen_netwerk(segmenten, knopen):
        knopen_netwerk = "knopenSplit_tmp2eersteSelectieKnopen"
        # selecteer knopen van netwerksegmenten
        wk_oidn_netwerksegmenten = tuple(set(
            val
            for row in arcpy.da.SearchCursor(segmenten, ["B_WK_OIDN", "E_WK_OIDN"])
            for val in row
        ))
        where_clause = f"WK_OIDN IN {wk_oidn_netwerksegmenten}"
        arcpy.ExportFeatures_conversion(knopen, knopen_netwerk, where_clause)

        return knopen_netwerk

    def selectie_knooptype_kruispunt(knopen_netwerk, segmenten):
        knopen_knooptype_kruispunt = "knopenSplit_tmp3tweedeSelectieKruispuntknopen"
        # berekenening knooptype met selectie van segmenten zodat er minder 'echte kruispunten' zijn
        f_knooptype = "knooptype_selectie"
        WegenregisterAnalyse.wegknooptype(knopen_netwerk, segmenten,f_knooptype="knooptype_selectie",spjoin="knopenSplit_tmp4spatialjoin")
        arcpy.ExportFeatures_conversion(
            in_features=knopen_netwerk,
            out_features=knopen_knooptype_kruispunt,
            where_clause=f"{f_knooptype} = 'knopen_overig'"

        )
        arcpy.AddMessage(
            f"{arcpy.GetCount_management(knopen_knooptype_kruispunt)[0]} knopen in {knopen_knooptype_kruispunt} na selectie 1")

        return knopen_knooptype_kruispunt

    def selecteer_bijkomende_kruispuntknopen(knopen_knooptype_kruispunt, knopen_netwerk, wbn, segmenten):
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
        #bereken knopen op aangepaste selectie segmenten
        segmenten_lr = "segmenten_selectie_morf"
        arcpy.MakeFeatureLayer_management(
            in_features=segmenten,
            out_layer=segmenten_lr,
            where_clause="LBLMORF IN ('weg bestaande uit één rijbaan','weg met gescheiden rijbanen die geen autosnelweg is')"
        )
        f_knooptype = "knooptype_selectie2"
        WegenregisterAnalyse.wegknooptype(knopen_netwerk, segmenten_lr, f_knooptype=f_knooptype,spjoin="wegknopen_spjoin2")
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
        #TOEVOEGEN,INTERSECT MORFOLOGIE GESCHEIDEN RIJBAAN
        bijkomende_kruispuntknopen = "knopenSplit_tmp5bijkomendeKruispuntknopen"
        arcpy.ExportFeatures_conversion(
            in_features=knopen_netwerk_lr,
            out_features=bijkomende_kruispuntknopen
        )
        return bijkomende_kruispuntknopen

    knopen_netwerk = selectie_knopen_netwerk(netwerksegmenten_intersect_merge, knopen)
    knopen_knooptype_kruispunt = selectie_knooptype_kruispunt(knopen_netwerk, netwerksegmenten_intersect_merge)
    knopen_rotonde = "knopenSplit_tmp6selectieRotondeknopen"
    WegenregisterAnalyse.bijkomende_rotonde_knopen(
        in_wegsegment=netwerksegmenten_intersect_merge,
        in_wegknopen_geselecteerd=knopen_knooptype_kruispunt,
        in_wegknopen_preselectie=knopen_netwerk,
        out_wegknoop=knopen_rotonde
    )
    bijkomende_kruispuntknopen = selecteer_bijkomende_kruispuntknopen(
        knopen_knooptype_kruispunt,
        knopen_netwerk,
        wbn,
        segmenten
    )

    arcpy.Merge_management(
        inputs=[knopen_knooptype_kruispunt, knopen_rotonde, bijkomende_kruispuntknopen],
        output=knopen_split
    )
    arcpy.AddMessage(f"{arcpy.GetCount_management(knopen_split)[0]} knopen in {knopen_split}")
    return knopen_split


def segmenteer_netwerk(netwerk_niet_gesegmenteerd, knopen_netwerksegmenten_split):
    netwerk_gesegmenteerd = "netwerksegmenten"

    print(f"Bestaat netwerk ({netwerk_niet_gesegmenteerd})?", arcpy.Exists(netwerk_niet_gesegmenteerd))
    print(f"Bestaat knopen ({knopen_netwerksegmenten_split})?", arcpy.Exists(knopen_netwerksegmenten_split))
    print("Aantal lijnen:", arcpy.GetCount_management(netwerk_niet_gesegmenteerd))
    print("Aantal knopen:", arcpy.GetCount_management(knopen_netwerksegmenten_split))

    if arcpy.Exists(netwerk_gesegmenteerd):
        print("delete")
        arcpy.Delete_management(netwerk_gesegmenteerd)

    arcpy.SplitLineAtPoint_management(
        in_features=netwerk_niet_gesegmenteerd,
        point_features=knopen_netwerksegmenten_split,
        out_feature_class=netwerk_gesegmenteerd,
        search_radius="0,001 Meters"
    )
    return netwerk_gesegmenteerd
