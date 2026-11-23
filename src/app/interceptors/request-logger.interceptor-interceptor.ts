import { HttpInterceptorFn,HttpEventType,HttpErrorResponse } from '@angular/common/http';
import {tap} from 'rxjs/operators';


export const requestLoggerInterceptorInterceptor: HttpInterceptorFn = (req, next) => {
  console.info(`[HTTP Request] ${req.method}${req.url}`);
  return next(req).pipe(
    tap({
      next:event=>{
        if(event.type===HttpEventType.Response){
          console.info(`[HTTP Response] ${req.method}${req.url} -> ${event.status}`);
        }
      },
      error:(error:HttpErrorResponse)=>{
       console.warn(
        `[HTTP Error] ${req.method}${req.url} -> ${error.status}`
       )

      }
    })
  );
};
