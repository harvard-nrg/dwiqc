package org.apache.turbine.app.xnat.modules.screens;

import org.apache.turbine.util.RunData;
import org.apache.velocity.context.Context;
import org.nrg.xdat.model.XnatAbstractresourceI;
import org.nrg.xdat.om.NeuroinfoDwiqc;
import org.nrg.xdat.om.XnatResource;
import org.nrg.xdat.turbine.modules.screens.SecureReport;

import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

public class XDATScreen_report_neuroinfo_dwiqc extends SecureReport {
    @Override
    public void finalProcessing(RunData data, Context context) {
        NeuroinfoDwiqc neuroinfoDwiqc = new NeuroinfoDwiqc( item);
        context.put("om",om);
        List<XnatAbstractresourceI> out_file = neuroinfoDwiqc.getOut_file();
        Map<String,String> map = out_file.stream()
                .filter( f -> f instanceof XnatResource)
                .map( f -> (XnatResource) f)
                .collect( Collectors.toMap( XnatResource::getLabel, XnatResource::getUri));
        context.put( "fileMap", map);
    }
}
